"""
Tabla de precios por modelo (USD por 1M tokens) y utilidades de proyección
de coste a escala. Los precios de OpenAI se usan para el cálculo REAL
(el modelo que efectivamente genera el examen); los precios de Claude se
usan para la comparativa PROYECTADA (no se llama a la API de Anthropic en
esta demo: se aplica el mismo recuento real de tokens de la llamada
ejecutada a las tarifas publicadas de cada modelo, para poder comparar
manzanas con manzanas sobre la MISMA carga de trabajo).

Precios de referencia (USD / 1,000,000 tokens), verificados en la fecha
de esta demo. Se muestran también en el README para que puedan
actualizarse fácilmente si las tarifas cambian.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PrecioModelo:
    nombre: str
    proveedor: str
    precio_input_1m: float   # USD por 1M tokens de entrada (prompt)
    precio_output_1m: float  # USD por 1M tokens de salida (completion)


TABLA_PRECIOS: dict[str, PrecioModelo] = {
    "gpt-4o-mini": PrecioModelo(
        nombre="GPT-4o-mini",
        proveedor="OpenAI",
        precio_input_1m=0.150,
        precio_output_1m=0.600,
    ),
    "claude-3-5-haiku": PrecioModelo(
        nombre="Claude 3.5 Haiku",
        proveedor="Anthropic",
        precio_input_1m=0.80,
        precio_output_1m=4.00,
    ),
    "claude-3-5-sonnet": PrecioModelo(
        nombre="Claude 3.5 Sonnet",
        proveedor="Anthropic",
        precio_input_1m=3.00,
        precio_output_1m=15.00,
    ),
}

EUR_POR_USD = 0.92  # tipo de cambio aproximado, ajustable en README/UI

# Mapeo de nuestras claves internas (usadas en TABLA_PRECIOS y en la UI) al
# identificador real de modelo que espera la API de OpenRouter. OpenRouter
# expone un único endpoint compatible con la API de OpenAI y enruta cada
# petición al proveedor real (OpenAI, Anthropic, etc.) según este string.
OPENROUTER_MODEL_IDS: dict[str, str] = {
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "claude-3-5-haiku": "anthropic/claude-3.5-haiku",
    "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
}


def coste_usd(prompt_tokens: int, completion_tokens: int, modelo_key: str) -> float:
    """Devuelve el coste en USD de una llamada dada (tokens reales) para un modelo."""
    precio = TABLA_PRECIOS[modelo_key]
    coste = (
        (prompt_tokens / 1_000_000) * precio.precio_input_1m
        + (completion_tokens / 1_000_000) * precio.precio_output_1m
    )
    return coste


def coste_centimos_eur(prompt_tokens: int, completion_tokens: int, modelo_key: str) -> float:
    """Coste en céntimos de euro (1 EUR = 100 céntimos)."""
    usd = coste_usd(prompt_tokens, completion_tokens, modelo_key)
    eur = usd * EUR_POR_USD
    return eur * 100


def proyeccion_escala(
    prompt_tokens: int, completion_tokens: int, modelo_key: str, num_examenes: int
) -> float:
    """Proyección de coste total en EUR para N exámenes concurrentes/diarios."""
    centimos_unitarios = coste_centimos_eur(prompt_tokens, completion_tokens, modelo_key)
    total_centimos = centimos_unitarios * num_examenes
    return total_centimos / 100  # EUR
