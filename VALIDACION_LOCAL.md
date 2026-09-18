# Fase 4 — Ejecución y validación en local (Windows)

Con el venv ya activado (`.\venv\Scripts\Activate.ps1`):

```powershell
# 1. Crear tu .env real a partir de la plantilla
Copy-Item .env.example .env
notepad .env   # pega tu OPENAI_API_KEY real y guarda

# 2. Arrancar la app en el puerto 8501 (ya verificado como libre)
streamlit run app.py --server.port 8501
```

Streamlit abrirá automáticamente `http://localhost:8501` en tu navegador.

## Checklist de validación funcional

1. **Sin API key ni en .env ni en la UI** → el botón "Generar examen" debe
   aparecer deshabilitado y el sidebar debe mostrar el aviso ⚠️ amarillo.
2. **Pulsa "Cargar ejemplo de prueba"** → el textarea se rellena con el texto
   de Fisiología. El contador debe mostrar "✓ N caracteres — listo para generar."
3. **Escribe menos de 150 caracteres a mano** → debe aparecer el aviso azul
   informativo con el contador de progreso, y no debe romper la app.
4. **Introduce una API key inválida** (ej. `sk-invalida123`) y genera → debe
   aparecer un `st.error` legible ("La API Key de OpenAI es inválida..."),
   nunca una traza de Python cruda.
5. **Introduce una API key válida y genera** → deben aparecer:
   - Las 5 preguntas con 4 opciones cada una.
   - Badge 🟢/🔴 de verificación de cita en cada pregunta.
   - Métricas de latencia y tokens (prompt/completion) con valores > 0.
   - Tabla comparativa de coste entre los 3 modelos, ordenada de más barato
     a más caro, y el mensaje de ahorro porcentual.
   - Gráfico de barras de coste por modelo.
6. **Genera un segundo examen en la misma sesión** → debe aparecer el
   expander "Histórico de llamadas de esta sesión" con ambas filas.
7. **Cambia el número de exámenes a proyectar en el sidebar** (ej. a 100.000)
   → la columna de proyección de la tabla debe recalcularse sin volver a
   llamar a la API (es cálculo local, no requiere nueva inferencia).
