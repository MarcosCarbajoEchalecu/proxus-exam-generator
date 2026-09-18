# Fase 1 — Setup en Windows (Warp / PowerShell)

```powershell
# 1. Ir a la carpeta del proyecto
cd C:\Users\<TU_USUARIO>\proxus-demo

# 2. Crear entorno virtual con Python 3.13
C:\Python313\python.exe -m venv venv

# 3. Activar el entorno (ya tienes la política de ejecución en Bypass)
.\venv\Scripts\Activate.ps1

# 4. Confirmar que pip apunta al venv (usa siempre python -m pip)
python -m pip --version

# 5. Actualizar pip antes de instalar (evita fallos de resolución de wheels)
python -m pip install --upgrade pip

# 6. Instalar dependencias (todas son wheels binarias, no requieren compilador)
python -m pip install -r requirements.txt

# 7. Verificación rápida
python -c "import streamlit, langchain_openai, pydantic, tiktoken; print('OK - entorno listo')"
```

Si `pip install` intenta compilar algo (verías `Building wheel for X`), es señal de que
una dependencia transitiva no tiene wheel para 3.13 todavía. Con las versiones fijadas
arriba (verificadas a fecha de esta demo) esto no debería ocurrir.
