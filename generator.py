"""
Motor de generación de exámenes.

Responsabilidades:
1. Construir la cadena LangChain con salida estructurada (Pydantic) sobre
   GPT-4o-mini (modelo real y económico usado en producción).
2. Extraer telemetría REAL de la llamada: latencia medida en wall-clock y
   tokens prompt/completion extraídos de `response_metadata` /
   `usage_metadata` de la respuesta del modelo (no estimados con tiktoken,
   salvo como fallback si el proveedor no los devuelve).
3. Validar el anclaje documental: cada `cita_textual_literal` debe ser una
   subcadena EXACTA del texto fuente. Si no lo es, la pregunta se marca
   como "no verificada" en lugar de descartarse silenciosamente, para que
   la UI pueda mostrar honestamente el nivel de fiabilidad del anclaje.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from openai import AuthenticationError, RateLimitError, APIConnectionError, APIError
from pydantic import ValidationError

from schemas import ExamenGenerado, PreguntaExamen
from pricing import OPENROUTER_MODEL_IDS

MIN_CARACTERES_TEXTO = 150
NUM_PREGUNTAS_DEFECTO = 5

# OpenRouter expone un endpoint único, compatible con la API de OpenAI, que
# enruta cada petición al proveedor real (OpenAI, Anthropic...) según el
# nombre de modelo. Por eso basta con apuntar ChatOpenAI a esta base_url y
# usar una API key de OpenRouter (formato sk-or-v1-...) en vez de una de
# OpenAI directa.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

SYSTEM_PROMPT = """\
Eres un catedrático universitario experto en evaluación educativa, diseñando \
exámenes tipo test rigurosos para estudiantes de grado.

Se te proporcionará un fragmento de apuntes universitarios. Debes generar \
exactamente {num_preguntas} preguntas tipo test de nivel universitario, siguiendo \
estas reglas ESTRICTAS e innegociables:

1. ANCLAJE DOCUMENTAL OBLIGATORIO: cada pregunta debe poder responderse \
   ÚNICAMENTE con información presente en el texto proporcionado. Está \
   PROHIBIDO usar conocimiento externo no presente en el texto.
2. CITA LITERAL: el campo `cita_textual_literal` debe ser una copia EXACTA, \
   palabra por palabra (sin resumir, sin parafrasear, sin corregir errores \
   tipográficos), de un fragmento continuo del texto original que demuestre \
   por qué la opción correcta lo es. Si cambias una sola palabra del texto \
   original, la pregunta será rechazada por el sistema de validación.
3. DISTRACTORES DE CALIDAD: los 3 distractores deben representar errores \
   conceptuales REALES y comunes que cometen los estudiantes (confusiones \
   entre conceptos similares, inversión de causa-efecto, generalizaciones \
   incorrectas, mezclar mecanismos parecidos). Evita distractores obviamente \
   absurdos o triviales de descartar.
4. Cada pregunta debe tener exactamente 4 opciones, con exactamente 1 correcta.
5. Numera las preguntas de 1 a {num_preguntas} de forma secuencial.

Debes responder ÚNICAMENTE con un objeto JSON válido (sin texto adicional, sin \
Markdown, sin ```json), con EXACTAMENTE esta forma (aquí con 1 sola pregunta \
de ejemplo, pero tú debes generar {num_preguntas}):

{{
  "preguntas": [
    {{
      "numero": 1,
      "enunciado": "texto de la pregunta",
      "opciones": [
        {{"texto": "opción A", "es_correcta": false, "justificacion_error": "por qué es una trampa"}},
        {{"texto": "opción B", "es_correcta": true, "justificacion_error": ""}},
        {{"texto": "opción C", "es_correcta": false, "justificacion_error": "por qué es una trampa"}},
        {{"texto": "opción D", "es_correcta": false, "justificacion_error": "por qué es una trampa"}}
      ],
      "cita_textual_literal": "fragmento copiado literalmente del texto fuente",
      "nivel_dificultad": "intermedio"
    }}
  ]
}}

IMPORTANTE: el array "opciones" de cada pregunta debe cerrarse con "]" ANTES \
de escribir "cita_textual_literal" y "nivel_dificultad", que van FUERA del \
array de opciones, como hermanos de "opciones" dentro del mismo objeto de \
pregunta. Usa siempre comillas dobles, nunca comillas simples, para claves y \
valores de texto.

Texto fuente:
---
{texto_fuente}
---
"""


@dataclass
class TelemetriaLlamada:
    modelo: str
    latencia_segundos: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    tokens_estimados: bool = False  # True si tuvimos que caer al fallback tiktoken


@dataclass
class PreguntaValidada:
    pregunta: PreguntaExamen
    cita_verificada: bool
    motivo_no_verificada: Optional[str] = None


@dataclass
class ResultadoGeneracion:
    preguntas: list[PreguntaValidada] = field(default_factory=list)
    telemetria: Optional[TelemetriaLlamada] = None


class ErrorGeneracion(Exception):
    """Error de negocio, ya traducido a un mensaje apto para mostrar en la UI."""


def _normalizar_para_busqueda(texto: str) -> str:
    """Normaliza espacios/comillas/acentos ligeramente para hacer la
    comparación de substring más tolerante a diferencias triviales de
    espaciado sin relajar la exigencia de literalidad real del contenido."""
    texto = unicodedata.normalize("NFKC", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _verificar_cita(cita: str, texto_fuente: str) -> tuple[bool, Optional[str]]:
    if len(cita.strip()) < 10:
        return False, "La cita es demasiado corta para ser verificable."

    cita_norm = _normalizar_para_busqueda(cita)
    fuente_norm = _normalizar_para_busqueda(texto_fuente)

    if cita_norm in fuente_norm:
        return True, None

    return False, "La cita no se encontró como subcadena literal del texto fuente."


def _extraer_telemetria(respuesta_ai_message, modelo: str, latencia: float) -> TelemetriaLlamada:
    """Extrae tokens reales desde la metadata que devuelve el proveedor.

    LangChain expone en `AIMessage.usage_metadata` (formato normalizado) o,
    como alternativa, en `response_metadata['token_usage']` (formato nativo
    de OpenAI) los contadores reales de la llamada.
    """
    usage = getattr(respuesta_ai_message, "usage_metadata", None)
    if usage:
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        return TelemetriaLlamada(
            modelo=modelo,
            latencia_segundos=latencia,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            tokens_estimados=False,
        )

    token_usage = respuesta_ai_message.response_metadata.get("token_usage", {})
    if token_usage:
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        total_tokens = token_usage.get("total_tokens", prompt_tokens + completion_tokens)
        return TelemetriaLlamada(
            modelo=modelo,
            latencia_segundos=latencia,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            tokens_estimados=False,
        )

    # Fallback: si el proveedor no devolviera metadata (no debería ocurrir con
    # OpenAI), estimamos con tiktoken para no romper la UI de telemetría.
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    contenido = respuesta_ai_message.content if isinstance(respuesta_ai_message.content, str) else str(
        respuesta_ai_message.content
    )
    completion_tokens = len(enc.encode(contenido))
    return TelemetriaLlamada(
        modelo=modelo,
        latencia_segundos=latencia,
        prompt_tokens=0,
        completion_tokens=completion_tokens,
        total_tokens=completion_tokens,
        tokens_estimados=True,
    )


def _quitar_valla_markdown(texto: str) -> str:
    """Si el modelo envuelve el JSON en ```json ... ``` a pesar de habérselo
    prohibido, lo extrae igualmente en vez de fallar."""
    texto = texto.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", texto, re.DOTALL)
    if match:
        return match.group(1).strip()
    return texto


def _reparar_array_opciones_sin_cerrar(texto: str) -> str:
    """Arreglo heurístico para un fallo observado con modelos vía proxy:
    tras las 4 opciones del array `opciones`, el modelo a veces olvida el
    "]" de cierre antes de escribir "cita_textual_literal", dejando
    "cita_textual_literal" incorrectamente dentro del array. Esta función
    inserta el "]" que falta justo antes de la primera aparición de
    "cita_textual_literal" que venga precedida por un "}," de una opción,
    en lugar de por el cierre correcto del array.
    """
    # Inserta "]" antes de una clave "cita_textual_literal" que aparezca
    # justo después de cerrar un objeto de opción (patrón: '},"cita_textual_literal"'
    # o '}, "cita_textual_literal"') sin un "]" de por medio.
    patron = re.compile(r'\}\s*,\s*"cita_textual_literal"')

    def _insertar_cierre(m: re.Match) -> str:
        return "}]," + m.group(0)[m.group(0).index(",") + 1 :]

    return patron.sub(_insertar_cierre, texto)


def _quitar_llaves_sobrantes_al_final(texto: str) -> str:
    """Elimina un exceso patológico de '}' repetidas al final del texto
    (observado como bug de generación) hasta dejar los delimitadores
    balanceados según el conteo de '{' y '['."""
    apertura = texto.count("{") 
    cierre = texto.count("}")
    exceso = cierre - apertura
    if exceso > 0 and texto.rstrip().endswith("}" * min(exceso, 5)):
        # Recorta desde el final solo las llaves sobrantes, de una en una,
        # verificando que no rompamos JSON válido en el proceso.
        texto_recortado = texto.rstrip()
        recortadas = 0
        while recortadas < exceso and texto_recortado.endswith("}"):
            candidato = texto_recortado[:-1].rstrip()
            # No recortar más allá del cierre legítimo del objeto raíz.
            if candidato.count("{") == 0:
                break
            texto_recortado = candidato
            recortadas += 1
        return texto_recortado
    return texto


def _parsear_examen_con_reparacion(contenido: str) -> Optional[ExamenGenerado]:
    """Intenta interpretar la respuesta del modelo como un ExamenGenerado
    válido, aplicando una cascada de estrategias de reparación de JSON antes
    de rendirse. Devuelve None si ninguna estrategia funciona."""
    if not contenido or not contenido.strip():
        return None

    candidatos = [contenido]
    candidatos.append(_quitar_valla_markdown(contenido))
    candidatos.append(_reparar_array_opciones_sin_cerrar(_quitar_valla_markdown(contenido)))
    candidatos.append(
        _quitar_llaves_sobrantes_al_final(
            _reparar_array_opciones_sin_cerrar(_quitar_valla_markdown(contenido))
        )
    )

    try:
        from json_repair import repair_json

        candidatos.append(repair_json(_quitar_valla_markdown(contenido)))
        candidatos.append(
            repair_json(
                _quitar_llaves_sobrantes_al_final(
                    _reparar_array_opciones_sin_cerrar(_quitar_valla_markdown(contenido))
                )
            )
        )
    except ImportError:
        pass  # json_repair no instalado: seguimos solo con las heurísticas propias.

    for candidato in candidatos:
        if not candidato:
            continue
        try:
            data = json.loads(candidato)
        except (json.JSONDecodeError, TypeError):
            continue
        try:
            return ExamenGenerado.model_validate(data)
        except ValidationError:
            continue

    return None


def generar_examen(
    texto_fuente: str,
    api_key: str,
    num_preguntas: int = NUM_PREGUNTAS_DEFECTO,
    modelo: str = "gpt-4o-mini",
    temperatura: float = 0.4,
) -> ResultadoGeneracion:
    """
    Genera un examen tipo test a partir de `texto_fuente`, valida el anclaje
    documental de cada pregunta y devuelve preguntas + telemetría real.

    Lanza `ErrorGeneracion` con un mensaje ya apto para mostrar al usuario
    final en caso de fallo (clave inválida, texto corto, rate limit, etc.).
    """
    texto_fuente = (texto_fuente or "").strip()
    if len(texto_fuente) < MIN_CARACTERES_TEXTO:
        raise ErrorGeneracion(
            f"El texto ingresado tiene {len(texto_fuente)} caracteres. "
            f"Se requieren al menos {MIN_CARACTERES_TEXTO} para garantizar "
            "suficiente contexto pedagógico y evitar preguntas pobres o repetitivas."
        )

    if not api_key or not api_key.strip():
        raise ErrorGeneracion(
            "No se ha proporcionado una API Key de OpenRouter. Introduce una "
            "clave válida (formato sk-or-v1-...) en el panel lateral o "
            "configura la variable de entorno OPENAI_API_KEY."
        )

    modelo_openrouter = OPENROUTER_MODEL_IDS.get(modelo, modelo)

    try:
        llm = ChatOpenAI(
            model=modelo_openrouter,
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            temperature=temperatura,
            timeout=60,
            # max_tokens generoso: con 5 preguntas de 4 opciones + citas +
            # justificaciones de distractor, el JSON de salida puede superar
            # fácilmente el límite por defecto y truncarse a mitad de un
            # objeto.
            max_tokens=4000,
            # "json_object" pide al modelo que devuelva JSON puro como texto,
            # en vez de forzarlo a empaquetar la respuesta como argumentos de
            # una llamada a función (tool calling). Para JSON anidado con
            # varias preguntas, esto resulta más robusto a través de un
            # proxy como OpenRouter: hemos observado que el modo de "function
            # calling" clásico puede hacer que el modelo pierda la cuenta del
            # anidamiento (arrays sin cerrar, mezcla de comillas) al intentar
            # encajar una estructura compleja dentro del formato de argumentos
            # de función.
            model_kwargs={"response_format": {"type": "json_object"}},
            default_headers={
                # Recomendado (no obligatorio) por OpenRouter para
                # identificar la app en su dashboard de uso.
                "HTTP-Referer": "https://proxus-demo.streamlit.app",
                "X-Title": "PROXUS Demo - Generador de Examenes",
            },
        )

        prompt = ChatPromptTemplate.from_messages(
            [("system", SYSTEM_PROMPT), ("human", "Genera el examen ahora, solo el JSON.")]
        )
        cadena = prompt | llm

        inicio = time.perf_counter()
        mensaje_ai = cadena.invoke(
            {"num_preguntas": num_preguntas, "texto_fuente": texto_fuente}
        )
        latencia = time.perf_counter() - inicio

    except AuthenticationError:
        raise ErrorGeneracion(
            "La API Key de OpenRouter es inválida, ha sido revocada, o no "
            "tiene crédito/saldo disponible. Verifica la clave en "
            "openrouter.ai/keys e inténtalo de nuevo."
        )
    except RateLimitError:
        raise ErrorGeneracion(
            "Se ha alcanzado el límite de peticiones (rate limit) o de crédito "
            "disponible en tu cuenta de OpenRouter. Espera unos segundos o "
            "revisa tu saldo."
        )
    except APIConnectionError:
        raise ErrorGeneracion(
            "No se ha podido conectar con la API de OpenRouter. Verifica tu "
            "conexión a internet e inténtalo de nuevo."
        )
    except APIError as e:
        raise ErrorGeneracion(f"Error de la API de OpenRouter: {e}")
    except Exception as e:  # defensivo: nunca dejar caer una traza cruda a la UI
        raise ErrorGeneracion(f"Error inesperado generando el examen: {e}")

    contenido_crudo = mensaje_ai.content
    if isinstance(contenido_crudo, list):
        contenido_crudo = "".join(
            bloque.get("text", "") if isinstance(bloque, dict) else str(bloque)
            for bloque in contenido_crudo
        )

    examen_parseado = _parsear_examen_con_reparacion(contenido_crudo)

    if examen_parseado is None:
        preview = (contenido_crudo or "")[:800]
        raise ErrorGeneracion(
            "El modelo devolvió una respuesta que no se pudo interpretar como "
            "JSON válido, ni siquiera tras intentar repararla automáticamente. "
            "Puede ayudar reducir el número de preguntas o volver a intentarlo.\n\n"
            f"Contenido crudo devuelto (primeros 800 caracteres): {preview!r}"
        )

    telemetria = _extraer_telemetria(mensaje_ai, modelo, latencia)

    preguntas_validadas: list[PreguntaValidada] = []
    for pregunta in examen_parseado.preguntas:
        verificada, motivo = _verificar_cita(pregunta.cita_textual_literal, texto_fuente)
        preguntas_validadas.append(
            PreguntaValidada(pregunta=pregunta, cita_verificada=verificada, motivo_no_verificada=motivo)
        )

    return ResultadoGeneracion(preguntas=preguntas_validadas, telemetria=telemetria)
