"""
Esquemas Pydantic para la generación estructurada de exámenes tipo test.

Estos modelos son el "contrato de datos" que fuerza al LLM (vía structured
output / function-calling de LangChain) a devolver JSON válido, sin necesidad
de parsear texto libre ni de sufrir alucinaciones de formato.
"""

from typing import List, Literal
from pydantic import BaseModel, Field, field_validator


class OpcionRespuesta(BaseModel):
    """Una opción individual (distractor o correcta) de una pregunta tipo test."""

    texto: str = Field(
        ...,
        description="Texto completo de la opción de respuesta, redactado a nivel universitario.",
        min_length=3,
    )
    es_correcta: bool = Field(
        ...,
        description="True únicamente si esta es la opción correcta según el texto fuente.",
    )
    justificacion_error: str = Field(
        default="",
        description=(
            "Si es un distractor (es_correcta=False), explica en una frase "
            "qué error conceptual común del estudiante representa esta trampa. "
            "Si es la opción correcta, dejar vacío."
        ),
    )


class PreguntaExamen(BaseModel):
    """
    Una pregunta tipo test con anclaje documental obligatorio.

    El campo `cita_textual_literal` es la pieza crítica anti-alucinación:
    el LLM debe copiar textualmente (no parafrasear) el fragmento del texto
    fuente que justifica la opción correcta. Este campo se valida después
    por código (substring match) contra el texto original.
    """

    numero: int = Field(..., description="Número de la pregunta, empezando en 1.")
    enunciado: str = Field(
        ...,
        description="Enunciado de la pregunta, claro y de nivel universitario.",
        min_length=10,
    )
    opciones: List[OpcionRespuesta] = Field(
        ...,
        description="Exactamente 4 opciones, de las cuales solo una tiene es_correcta=True.",
        min_length=4,
        max_length=4,
    )
    cita_textual_literal: str = Field(
        ...,
        description=(
            "Fragmento copiado LITERALMENTE (palabra por palabra, sin cambiar "
            "ni una letra) del texto fuente proporcionado, que demuestra por qué "
            "la opción marcada como correcta lo es. Debe ser una subcadena exacta "
            "del texto original, de entre 8 y 40 palabras."
        ),
        min_length=15,
    )
    nivel_dificultad: Literal["básico", "intermedio", "avanzado"] = Field(
        default="intermedio",
        description="Nivel de dificultad universitario estimado de la pregunta.",
    )

    @field_validator("opciones")
    @classmethod
    def validar_una_correcta(cls, opciones: List[OpcionRespuesta]) -> List[OpcionRespuesta]:
        correctas = sum(1 for o in opciones if o.es_correcta)
        if correctas != 1:
            raise ValueError(
                f"Debe haber exactamente 1 opción correcta, se encontraron {correctas}."
            )
        return opciones


class ExamenGenerado(BaseModel):
    """Contenedor de las N preguntas generadas para un examen."""

    preguntas: List[PreguntaExamen] = Field(
        ...,
        description="Lista de preguntas del examen generado.",
        min_length=1,
    )
