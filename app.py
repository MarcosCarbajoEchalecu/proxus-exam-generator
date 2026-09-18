"""
Demo — Generador de exámenes con anclaje documental estricto y telemetría
de coste por inferencia. Construido para la candidatura a Product Engineer
(AI & Full Stack) en PROXUS.

Ejecutar: streamlit run app.py
"""

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ejemplo_texto import TEXTO_EJEMPLO_FISIOLOGIA, METADATOS_EJEMPLO
from generator import (
    ErrorGeneracion,
    MIN_CARACTERES_TEXTO,
    NUM_PREGUNTAS_DEFECTO,
    generar_examen,
)
from pricing import TABLA_PRECIOS, coste_centimos_eur, proyeccion_escala

load_dotenv()  # Carga .env en local; no tiene efecto si no existe (p.ej. en Cloud)

st.set_page_config(
    page_title="PROXUS Demo — Generador de Exámenes con Anclaje Documental",
    page_icon="📚",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Estilos custom — tipografía, tarjetas y acentos de marca
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Oculta el menú/footer por defecto de Streamlit para un look más "producto" */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: rgba(0,0,0,0);}

    /* Cabecera hero con gradiente de marca */
    .proxus-hero {
        padding: 1.75rem 2rem;
        border-radius: 16px;
        background: linear-gradient(135deg, #5B4FE9 0%, #8B7FF0 55%, #3A2FD8 100%);
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 24px rgba(91, 79, 233, 0.25);
    }
    .proxus-hero h1 {
        color: white !important;
        font-size: 2rem;
        font-weight: 800;
        margin: 0 0 0.4rem 0;
        line-height: 1.2;
    }
    .proxus-hero p {
        color: rgba(255,255,255,0.92);
        font-size: 1.02rem;
        margin: 0;
        max-width: 780px;
    }
    .proxus-badges {
        margin-top: 1rem;
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
    }
    .proxus-badge {
        background: rgba(255,255,255,0.18);
        color: white;
        font-size: 0.78rem;
        font-weight: 600;
        padding: 0.3rem 0.7rem;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.35);
        backdrop-filter: blur(4px);
    }

    /* Tarjetas de pregunta con borde de color según verificación */
    .pregunta-card {
        border-radius: 12px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.9rem;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
    }
    .pregunta-card.verificada {
        border-left: 4px solid #22C55E;
    }
    .pregunta-card.no-verificada {
        border-left: 4px solid #EF4444;
    }
    .pregunta-numero {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        background: #5B4FE9;
        color: white;
        font-weight: 700;
        font-size: 0.85rem;
        margin-right: 0.5rem;
    }
    .badge-pill {
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.18rem 0.6rem;
        border-radius: 999px;
        margin-left: 0.4rem;
        letter-spacing: 0.02em;
    }
    .badge-verificada {
        background: rgba(34,197,94,0.15);
        color: #22C55E;
        border: 1px solid rgba(34,197,94,0.4);
    }
    .badge-no-verificada {
        background: rgba(239,68,68,0.15);
        color: #EF4444;
        border: 1px solid rgba(239,68,68,0.4);
    }
    .badge-nivel {
        background: rgba(148,163,184,0.15);
        color: #94A3B8;
        border: 1px solid rgba(148,163,184,0.3);
    }
    .opcion-correcta {
        background: rgba(34,197,94,0.08);
        border-radius: 8px;
        padding: 0.35rem 0.6rem;
        border-left: 3px solid #22C55E;
        margin: 0.25rem 0;
    }
    .opcion-distractor {
        padding: 0.35rem 0.6rem;
        margin: 0.25rem 0;
        color: rgba(255,255,255,0.85);
    }
    .cita-anclaje {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        color: #94A3B8;
        background: rgba(148,163,184,0.06);
        border-radius: 6px;
        padding: 0.5rem 0.7rem;
        margin-top: 0.5rem;
        border: 1px dashed rgba(148,163,184,0.25);
    }

    /* Tarjetas de métrica de telemetría */
    .metric-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1rem 1.1rem;
        text-align: center;
    }
    .metric-card .metric-icon { font-size: 1.3rem; }
    .metric-card .metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #F8FAFC;
        font-family: 'JetBrains Mono', monospace;
        margin: 0.15rem 0;
    }
    .metric-card .metric-label {
        font-size: 0.78rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .proxus-footer {
        margin-top: 2.5rem;
        padding-top: 1.2rem;
        border-top: 1px solid rgba(255,255,255,0.08);
        text-align: center;
        color: #64748B;
        font-size: 0.82rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------
if "resultado" not in st.session_state:
    st.session_state.resultado = None
if "texto_entrada" not in st.session_state:
    st.session_state.texto_entrada = ""
if "historial_telemetria" not in st.session_state:
    st.session_state.historial_telemetria = []  # lista de dicts para comparar llamadas


def _resolver_api_key(api_key_input: str) -> str:
    """Prioriza la clave introducida en la UI; si está vacía, cae a variable
    de entorno (.env local o Secrets en Streamlit Cloud)."""
    if api_key_input and api_key_input.strip():
        return api_key_input.strip()
    return os.getenv("OPENAI_API_KEY", "")


# ---------------------------------------------------------------------------
# Sidebar — configuración y credenciales
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Configuración")

    api_key_input = st.text_input(
        "OpenRouter API Key",
        type="password",
        placeholder="sk-or-v1-...",
        help=(
            "Usamos OpenRouter (endpoint único con acceso a GPT-4o-mini y "
            "Claude) en vez de OpenAI directo. Consíguela en "
            "openrouter.ai/keys. Se usa solo en esta sesión, nunca se "
            "almacena. Si la dejas vacía, se intentará leer de la variable "
            "de entorno OPENAI_API_KEY (.env local o Secrets en Streamlit Cloud)."
        ),
    )

    api_key_efectiva = _resolver_api_key(api_key_input)
    fuente_key = "Introducida manualmente" if (api_key_input and api_key_input.strip()) else "Variable de entorno"

    if api_key_efectiva:
        st.success(f"🔑 Clave de OpenRouter detectada ({fuente_key})", icon="✅")
    else:
        st.warning(
            "No se detecta ninguna API Key de OpenRouter. Introduce una arriba "
            "o configura OPENAI_API_KEY en tu entorno.",
            icon="⚠️",
        )

    st.divider()

    modelo_generacion = st.selectbox(
        "Modelo de generación (real)",
        options=list(TABLA_PRECIOS.keys()),
        index=0,
        format_func=lambda k: f"{TABLA_PRECIOS[k].nombre} ({TABLA_PRECIOS[k].proveedor})",
        help="Modelo que ejecutará realmente la llamada de generación.",
    )

    num_preguntas = st.slider("Número de preguntas", min_value=3, max_value=10, value=NUM_PREGUNTAS_DEFECTO)

    st.divider()
    st.markdown("### 📊 Escala de negocio")
    num_examenes_escala = st.number_input(
        "Exámenes concurrentes a proyectar",
        min_value=1_000,
        max_value=500_000,
        value=50_000,
        step=1_000,
        help="Volumen sobre el que se proyecta el coste total en la sección de telemetría.",
    )

    st.divider()
    st.caption(
        "Demo técnica construida para PROXUS (Lara) — anclaje documental "
        "estricto + telemetría de coste por inferencia."
    )

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="proxus-hero">
        <h1>📚 Generador de Exámenes con Anclaje Documental Estricto</h1>
        <p>Genera preguntas tipo test <strong>ancladas obligatoriamente a citas literales</strong>
        del texto fuente, con <strong>telemetría real de coste por inferencia</strong>
        comparada entre proveedores.</p>
        <div class="proxus-badges">
            <span class="proxus-badge">🛡️ Cero alucinaciones verificado por código</span>
            <span class="proxus-badge">⚡ GPT-4o-mini · Claude 3.5 Haiku · Claude 3.5 Sonnet</span>
            <span class="proxus-badge">📊 Telemetría en tiempo real</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col_input, col_info = st.columns([2, 1])

with col_input:
    st.markdown("#### 1️⃣ Texto fuente (apuntes universitarios)")

    if st.button("📥 Cargar ejemplo de prueba (Fisiología muscular)", use_container_width=True):
        st.session_state.texto_entrada = TEXTO_EJEMPLO_FISIOLOGIA

    texto_entrada = st.text_area(
        "Pega aquí el fragmento de apuntes",
        value=st.session_state.texto_entrada,
        height=280,
        placeholder=(
            "Pega un fragmento de apuntes universitarios (mínimo "
            f"{MIN_CARACTERES_TEXTO} caracteres)..."
        ),
        key="texto_entrada_widget",
    )
    st.session_state.texto_entrada = texto_entrada

    num_caracteres = len(texto_entrada.strip())
    if 0 < num_caracteres < MIN_CARACTERES_TEXTO:
        st.info(
            f"📏 {num_caracteres} / {MIN_CARACTERES_TEXTO} caracteres mínimos. "
            "Añade más contexto para generar preguntas de calidad.",
            icon="ℹ️",
        )
    elif num_caracteres >= MIN_CARACTERES_TEXTO:
        st.caption(f"✓ {num_caracteres} caracteres — listo para generar.")

    generar = st.button(
        "🚀 Generar examen",
        type="primary",
        use_container_width=True,
        disabled=not api_key_efectiva,
    )

with col_info:
    st.markdown("#### ℹ️ Cómo funciona")
    st.markdown(
        """
1. El texto se envía con un **esquema Pydantic obligatorio** (structured output).
2. Cada pregunta debe incluir una **cita literal** del texto.
3. El sistema **valida por código** (substring exacto) que la cita existe
   realmente en el texto fuente — si no, la pregunta se marca como
   **"no verificada"** en vez de descartarse silenciosamente.
4. Se mide la **latencia real** y se extraen los **tokens reales** de la
   metadata de la respuesta del proveedor.
        """
    )

# ---------------------------------------------------------------------------
# Generación
# ---------------------------------------------------------------------------
if generar:
    if not api_key_efectiva:
        st.error("Falta la API Key de OpenAI. Introdúcela en el panel lateral.", icon="🚫")
    else:
        with st.spinner(f"Generando {num_preguntas} preguntas con {TABLA_PRECIOS[modelo_generacion].nombre}..."):
            try:
                resultado = generar_examen(
                    texto_fuente=texto_entrada,
                    api_key=api_key_efectiva,
                    num_preguntas=num_preguntas,
                    modelo=modelo_generacion,
                )
                st.session_state.resultado = resultado
                st.session_state.historial_telemetria.append(
                    {
                        "modelo": resultado.telemetria.modelo,
                        "latencia_s": round(resultado.telemetria.latencia_segundos, 2),
                        "prompt_tokens": resultado.telemetria.prompt_tokens,
                        "completion_tokens": resultado.telemetria.completion_tokens,
                    }
                )
                st.success("Examen generado correctamente.", icon="✅")
            except ErrorGeneracion as e:
                st.error(str(e), icon="🚫")
                st.session_state.resultado = None

# ---------------------------------------------------------------------------
# Resultados: preguntas
# ---------------------------------------------------------------------------
resultado = st.session_state.resultado

if resultado:
    st.divider()
    st.markdown("### 2️⃣ Examen generado")

    n_verificadas = sum(1 for p in resultado.preguntas if p.cita_verificada)
    n_total = len(resultado.preguntas)
    ratio = n_verificadas / n_total if n_total else 0

    if ratio == 1.0:
        st.success(
            f"🛡️ Anclaje documental: {n_verificadas}/{n_total} preguntas con cita "
            "verificada literalmente en el texto fuente.",
            icon="✅",
        )
    else:
        st.warning(
            f"🛡️ Anclaje documental: {n_verificadas}/{n_total} preguntas con cita "
            "verificada. Las restantes se muestran igualmente, marcadas como "
            "no verificadas, para transparencia total.",
            icon="⚠️",
        )

    for pv in resultado.preguntas:
        pregunta = pv.pregunta
        clase_borde = "verificada" if pv.cita_verificada else "no-verificada"
        badge_html = (
            '<span class="badge-pill badge-verificada">🟢 CITA VERIFICADA</span>'
            if pv.cita_verificada
            else '<span class="badge-pill badge-no-verificada">🔴 CITA NO VERIFICADA</span>'
        )

        opciones_html = ""
        for i, opcion in enumerate(pregunta.opciones, start=1):
            letra = chr(64 + i)
            if opcion.es_correcta:
                opciones_html += (
                    f'<div class="opcion-correcta">✅ <strong>{letra}) {opcion.texto}</strong></div>'
                )
            else:
                detalle = f" — <em>trampa: {opcion.justificacion_error}</em>" if opcion.justificacion_error else ""
                opciones_html += f'<div class="opcion-distractor">{letra}) {opcion.texto}{detalle}</div>'

        if pv.cita_verificada:
            cita_html = f'<div class="cita-anclaje">📌 {pregunta.cita_textual_literal}</div>'
        else:
            cita_html = (
                f'<div class="cita-anclaje">⚠️ No verificada ({pv.motivo_no_verificada}): '
                f'{pregunta.cita_textual_literal}</div>'
            )

        st.markdown(
            f"""
            <div class="pregunta-card {clase_borde}">
                <div>
                    <span class="pregunta-numero">{pregunta.numero}</span>
                    <strong style="font-size:1.02rem;">{pregunta.enunciado}</strong>
                </div>
                <div style="margin: 0.5rem 0 0.7rem 2.1rem;">
                    {badge_html}
                    <span class="badge-pill badge-nivel">{pregunta.nivel_dificultad.upper()}</span>
                </div>
                <div style="margin-left: 2.1rem;">
                    {opciones_html}
                    {cita_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------------
    # Telemetría
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("### 3️⃣ Telemetría de inferencia y coste")

    t = resultado.telemetria
    c1, c2, c3, c4 = st.columns(4)
    metricas = [
        (c1, "⏱️", f"{t.latencia_segundos:.2f} s", "Latencia"),
        (c2, "📥", f"{t.prompt_tokens:,}", "Prompt tokens"),
        (c3, "📤", f"{t.completion_tokens:,}", "Completion tokens"),
        (c4, "Σ", f"{t.total_tokens:,}", "Total tokens"),
    ]
    for columna, icono, valor, etiqueta in metricas:
        with columna:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-icon">{icono}</div>
                    <div class="metric-value">{valor}</div>
                    <div class="metric-label">{etiqueta}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if t.tokens_estimados:
        st.caption(
            "⚠️ El proveedor no devolvió metadata de tokens en esta llamada; "
            "los completion tokens mostrados son una estimación vía tiktoken."
        )

    st.markdown("#### 💰 Comparativa de coste por modelo (misma carga de trabajo)")
    st.caption(
        "Se toma el recuento REAL de tokens de esta llamada "
        f"({t.prompt_tokens:,} prompt + {t.completion_tokens:,} completion) y se "
        "aplica a las tarifas públicas de cada modelo, para comparar el coste "
        "de haber generado este mismo examen con cada proveedor."
    )

    filas = []
    for key, precio in TABLA_PRECIOS.items():
        centimos = coste_centimos_eur(t.prompt_tokens, t.completion_tokens, key)
        proyeccion = proyeccion_escala(t.prompt_tokens, t.completion_tokens, key, int(num_examenes_escala))
        filas.append(
            {
                "Modelo": f"{precio.nombre} ({precio.proveedor})",
                "Coste por examen (céntimos €)": round(centimos, 4),
                f"Proyección a {int(num_examenes_escala):,} exámenes (€)": round(proyeccion, 2),
            }
        )

    df_costes = pd.DataFrame(filas).sort_values(
        by="Coste por examen (céntimos €)", ascending=True
    ).reset_index(drop=True)

    df_costes_mostrar = df_costes.copy()
    df_costes_mostrar.loc[0, "Modelo"] = "🏆 " + df_costes_mostrar.loc[0, "Modelo"]

    def _resaltar_mas_barato(fila):
        if fila.name == 0:
            return ["background-color: rgba(34,197,94,0.12); font-weight: 600;"] * len(fila)
        return [""] * len(fila)

    st.dataframe(
        df_costes_mostrar.style.apply(_resaltar_mas_barato, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    modelo_mas_barato = df_costes.iloc[0]["Modelo"]
    modelo_mas_caro = df_costes.iloc[-1]["Modelo"]
    coste_barato = df_costes.iloc[0]["Coste por examen (céntimos €)"]
    coste_caro = df_costes.iloc[-1]["Coste por examen (céntimos €)"]

    if coste_caro > 0:
        ahorro_pct = (1 - coste_barato / coste_caro) * 100
        st.info(
            f"💡 Usar **{modelo_mas_barato}** en lugar de **{modelo_mas_caro}** para "
            f"esta carga de trabajo supone un ahorro del **{ahorro_pct:.1f}%** "
            "en el coste de inferencia, con el mismo volumen exacto de tokens.",
            icon="💡",
        )

    st.bar_chart(
        df_costes.set_index("Modelo")["Coste por examen (céntimos €)"],
        use_container_width=True,
    )

    # -----------------------------------------------------------------------
    # Histórico de llamadas de la sesión
    # -----------------------------------------------------------------------
    if len(st.session_state.historial_telemetria) > 1:
        with st.expander("📈 Histórico de llamadas de esta sesión"):
            st.dataframe(
                pd.DataFrame(st.session_state.historial_telemetria),
                use_container_width=True,
                hide_index=True,
            )

st.markdown(
    f"""
    <div class="proxus-footer">
        Fuente del texto de ejemplo: {METADATOS_EJEMPLO["fuente"]} · {METADATOS_EJEMPLO["titulo"]}<br>
        Demo técnica construida para <strong>PROXUS</strong> — Product Engineer (AI & Full Stack)
    </div>
    """,
    unsafe_allow_html=True,
)
