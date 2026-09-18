# Fase 5 — Subida a GitHub y despliegue en Streamlit Community Cloud

## 5.1 — Subir el repositorio a GitHub

Desde PowerShell, dentro de la carpeta del proyecto:

```powershell
git init
git add .
git status   # IMPORTANTE: confirma que .env NO aparece en la lista (gitignore)
git commit -m "Demo PROXUS: generador de examenes con anclaje documental y telemetria de coste"

# Crea el repo vacío en https://github.com/new (ej: proxus-demo-lara)
# Luego conecta el remoto (sustituye TU_USUARIO):
git branch -M main
git remote add origin https://github.com/TU_USUARIO/proxus-demo-lara.git
git push -u origin main
```

Si Git te pide login, con HTTPS te pedirá usuario + Personal Access Token
(no la contraseña normal de GitHub, que ya no se acepta por HTTPS).

## 5.2 — Desplegar gratis en Streamlit Community Cloud

1. Entra en **https://share.streamlit.io** y haz login con tu cuenta de GitHub.
2. Pulsa **"New app"**.
3. Selecciona:
   - **Repository**: `TU_USUARIO/proxus-demo-lara`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. Antes de darle a "Deploy", ve a **"Advanced settings" → "Secrets"** y pega:

   ```toml
   OPENAI_API_KEY = "sk-tu-clave-real-aqui"
   ```

   (Esto es exactamente el contenido de tu `.streamlit/secrets.toml.example`,
   pero con la clave real. Streamlit Cloud lo inyecta como variable de
   entorno, por lo que `os.getenv("OPENAI_API_KEY")` en `app.py` lo detecta
   automáticamente sin cambiar una línea de código.)

5. Pulsa **"Deploy"**. El primer build tarda 2-4 minutos instalando
   `requirements.txt`.
6. Tu app quedará publicada en una URL del tipo:
   `https://tu-usuario-proxus-demo-lara.streamlit.app`

## 5.3 — Actualizaciones posteriores

Cada `git push` a `main` redespliega automáticamente la app en Streamlit
Cloud (no hace falta ninguna acción manual adicional).

## 5.4 — Verificación post-despliegue

- Abre la URL pública **en una ventana de incógnito** (sin tu sesión) y
  confirma que:
  - El botón "Cargar ejemplo de prueba" funciona sin que el visitante
    necesite subir ningún archivo.
  - Si el visitante NO introduce su propia key, la app usa el Secret
    configurado y genera igualmente (esto es una decisión de producto: puedes
    optar por dejarlo así para la demo, o exigir key propia si prefieres
    controlar el gasto — ver nota de coste en el README).
