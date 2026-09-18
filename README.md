# Generador de Exámenes con Anclaje Documental Estricto y Telemetría de Coste
### Demo técnica para PROXUS — construida por [Tu Nombre]

> Demo en vivo: `https://TU-URL.streamlit.app` (rellenar tras despliegue)

---

## 1. Por qué existe esta demo

Lara sirve a más de 220.000 estudiantes universitarios con picos de uso
extremos en época de exámenes. En ese contexto, cualquier feature de
generación de contenido pedagógico con LLMs tiene **tres riesgos de negocio
simultáneos**, no solo uno técnico:

1. **Riesgo de confianza**: si un examen generado por IA inventa un dato que
   no está en los apuntes del estudiante, el producto pierde credibilidad
   académica de forma instantánea e irreversible.
2. **Riesgo de margen**: en un pico de examen con miles de peticiones
   concurrentes, la elección de modelo (y del diseño del prompt) puede
   suponer una diferencia de **10x-20x en factura de inferencia** para
   exactamente el mismo output percibido por el usuario.
3. **Riesgo de UX bajo carga**: si el sistema no degrada con elegancia
   (claves inválidas, rate limits, timeouts) durante el pico de mayor tráfico
   del año académico, el coste no es solo económico sino reputacional.

Esta demo ataca los tres a la vez, con código real y medible, no con
diapositivas.

---

## 2. Qué resuelve cada pieza (mapeado a los tres retos del enunciado)

### 2.1 Generación pedagógica con distractores de calidad
El prompt de sistema (`generator.py`) no pide "genera preguntas": pide
explícitamente que cada distractor represente **un error conceptual real y
común del estudiante** (confusión entre conceptos similares, inversión
causa-efecto, mezcla de mecanismos parecidos). Esto es lo que separa un
test-generator genérico de una herramienta que un profesor universitario
firmaría.

### 2.2 Anclaje documental estricto (cero alucinaciones)
Este es el punto más importante desde el punto de vista de producto, y es
donde la mayoría de demos de "IA generativa educativa" fallan:

- **No basta con pedirle al LLM que "no invente"**. Los LLMs alucinan citas
  con total confianza aunque se les prohíba expresamente.
- La solución aquí es **arquitectónica, no solo de prompting**: cada
  pregunta debe devolver un campo `cita_textual_literal` (forzado por el
  esquema Pydantic `PreguntaExamen`), y **el código —no el modelo— verifica
  por substring exacto** (`generator._verificar_cita`) que esa cita existe
  realmente, palabra por palabra, en el texto que subió el estudiante.
- Si la cita no se puede verificar, **la pregunta no se descarta
  silenciosamente**: se muestra igualmente marcada como "🔴 no verificada".
  Esto es una decisión de producto deliberada: en un contexto educativo,
  ocultar el fallo es peor que mostrarlo con transparencia. Permite además
  medir en producción qué % de preguntas pasan la verificación como métrica
  de calidad del prompt a lo largo del tiempo (una métrica que Lara podría
  llevar a un dashboard interno).

### 2.3 Telemetría de inferencia y comparativa de coste a escala
- Los tokens **no se estiman**: se extraen de `usage_metadata` /
  `response_metadata` de la respuesta real del proveedor. Solo si el
  proveedor no los devolviera (caso no esperado con OpenAI), se cae a una
  estimación con `tiktoken` marcada explícitamente como tal en la UI.
- La comparativa entre **GPT-4o-mini, Claude 3.5 Haiku y Claude 3.5 Sonnet**
  aplica el **mismo recuento real de tokens de la llamada ejecutada** a las
  tarifas publicadas de cada proveedor. Esto es intencional: aísla la
  variable de precio del proveedor de la variable de verbosidad del modelo,
  para que la comparación sea honesta y no una elección sesgada hacia el
  modelo "ganador".
- Se proyecta el coste a un volumen configurable (por defecto, **50.000
  exámenes concurrentes**, el escenario de un pico real de época de
  exámenes).

---

## 3. El ahorro del ~90%: de dónde sale exactamente

Con tarifas públicas por 1M de tokens (input / output):

| Modelo | Proveedor | Input | Output |
|---|---|---|---|
| GPT-4o-mini | OpenAI | $0.150 | $0.600 |
| Claude 3.5 Haiku | Anthropic | $0.80 | $4.00 |
| Claude 3.5 Sonnet | Anthropic | $3.00 | $15.00 |

Para una carga de trabajo representativa de este generador (prompt largo
por el texto fuente + 5 preguntas estructuradas de salida), **GPT-4o-mini
resulta entre 5x y 25x más barato por examen** que Sonnet, dependiendo de la
proporción prompt/completion real de cada tirada — la propia app calcula el
porcentaje exacto de ahorro en cada ejecución, en vivo, en lugar de dar una
cifra fija de marketing.

**La palanca de negocio no es "usar el modelo más barato siempre"**, es:

> Construir la arquitectura para que **cambiar de modelo sea una línea de
> configuración**, no una reescritura. Así, el equipo de PROXUS puede usar
> Haiku o Sonnet en tareas donde el razonamiento pedagógico sea más exigente
> (ej. feedback abierto, corrección de ensayos) y GPT-4o-mini en tareas de
> alto volumen y baja ambigüedad como este generador de tipo test — sin
> bloquear la decisión a un solo proveedor.

Esto es exactamente el tipo de decisión de ingeniería de producto que
protege el margen operativo en el pico de tráfico de exámenes, que es
cuando el coste de inferencia se dispara justo a la vez que sube la
exigencia de disponibilidad.

---

## 4. Decisiones de arquitectura relevantes para el equipo de PROXUS

- **Salida estructurada vía Pydantic + `with_structured_output`**, no
  parsing de texto libre con regex. Esto elimina una clase entera de bugs de
  producción (JSON malformado, campos faltantes) y es directamente
  extensible a otros tipos de contenido pedagógico (resúmenes, flashcards,
  feedback de ensayos) sin cambiar el patrón.
- **Errores de proveedor traducidos a mensajes de negocio**, nunca trazas de
  Python: `AuthenticationError`, `RateLimitError`, `APIConnectionError` se
  capturan y se convierten en `ErrorGeneracion` con texto apto para el
  usuario final. En un pico de examen con miles de estudiantes concurrentes,
  esto es lo que evita que un rate limit se convierta en un ticket de
  soporte masivo.
- **Desacoplamiento total de credenciales** (`_resolver_api_key`): funciona
  igual en local (`.env`), en producción (Secrets de Streamlit Cloud) o con
  clave aportada por el propio usuario en la UI — el mismo patrón que
  necesitaría cualquier feature de Lara que se despliegue en varios entornos.
- **Validación de anclaje separada de la generación**: `_verificar_cita` es
  una función pura, testeable de forma aislada (ver `generator.py`), lo cual
  significa que el umbral de "qué cuenta como verificado" puede ajustarse o
  reforzarse sin tocar el prompt ni volver a entrenar nada.

---

## 5. Cómo correrlo

Ver `SETUP_WINDOWS.md` (entorno), `VALIDACION_LOCAL.md` (checklist de
pruebas) y `DESPLIEGUE.md` (GitHub + Streamlit Cloud).

```powershell
streamlit run app.py --server.port 8501
```

---

## 6. Siguientes pasos si esto fuera a producción en Lara

1. **Dashboard agregado de coste por feature**, no solo por llamada:
   loggear cada `TelemetriaLlamada` a un almacén (ej. tabla en Postgres) para
   ver coste real diario/semanal desagregado por feature y por modelo.
2. **Selector automático de modelo por complejidad del texto de entrada**
   (longitud, densidad de tecnicismos) en lugar de un modelo fijo por
   feature, para no pagar precio de Sonnet en apuntes triviales.
3. **Cacheo de generación por hash del texto fuente**, ya que en época de
   exámenes es habitual que cientos de estudiantes de la misma asignatura
   suban fragmentos idénticos de los mismos apuntes compartidos.
4. **Test de regresión de calidad de distractores** con un set fijo de
   apuntes de referencia, para detectar si un cambio de prompt o de modelo
   degrada la calidad pedagógica antes de que lo note un usuario real.
