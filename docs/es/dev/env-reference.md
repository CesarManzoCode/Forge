# Referencia de Variables de Entorno

Referencia completa de todas las variables `.env` de Forge.

---

## Requeridas

| Variable | Descripción |
|----------|-------------|
| `GROQ_API_KEY` | Tu clave API de Groq. Obtén una gratis en [console.groq.com](https://console.groq.com) |
| `FORGE_PROJECT_ROOT` | Ruta absoluta al directorio de tu proyecto. Forge no puede acceder a archivos fuera de esta ruta. Ejemplo: `/home/usuario/miproyecto` |

---

## Configuración del LLM

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Modelo de Groq a usar. Recomendado: `llama-3.3-70b-versatile`. Los modelos más pequeños pueden producir JSON inconsistente. |
| `FORGE_LANGUAGE` | `English` | Idioma para las respuestas del agente. Ejemplo: `Spanish`, `French`, `German`. Afecta todos los prompts visibles al usuario y las descripciones de subtareas. |
| `FORGE_CONTEXT_LIMIT` | `128000` | Contexto máximo de tokens del modelo. Configura esto para que coincida con la ventana de contexto real de tu modelo. |
| `FORGE_COMPRESS_AT` | `0.80` | Fracción del límite de contexto en la que se activa la compresión del historial. `0.80` = comprimir cuando esté al 80% (~102k tokens). Valores más bajos comprimen más agresivamente. |

---

## Configuración de seguridad

| Variable | Default | Descripción |
|----------|---------|-------------|
| `FORGE_SANDBOX` | `true` | Activar sandbox de ejecución para `run_code()`. Cuando es `true`, los snippets de código se ejecutan en un directorio temporal aislado. Solo ponlo en `false` para debugging. |
| `FORGE_EXEC_TIMEOUT` | `30` | Segundos antes de que se mate una ejecución de código o comando de shell. Se aplica a `run_code()`, `run_file()` y `run_command()`. |
| `FORGE_ALLOWED_EXTENSIONS` | `.py,.js,.ts,.go,.rs,.rb,.java` | Lista separada por comas de extensiones de archivo que pueden ejecutarse via `run_code()`. Agregar `.sh` aquí no funciona — los scripts de shell están permanentemente bloqueados. |
| `FORGE_MAX_WRITE_BYTES` | `1048576` | Máximo de bytes que el agente puede escribir en una sola llamada a `write_file()`. Por defecto 1MB. |

---

## Configuración de tools

| Variable | Default | Descripción |
|----------|---------|-------------|
| `FORGE_MAX_STEPS` | `20` | Máximo de pasos ReAct por subtarea antes de que se fuerce al agente a detenerse. Aumenta para subtareas complejas, disminuye si el agente tiende a entrar en loop. |
| `FORGE_EXTRA_COMMANDS` | *(vacío)* | Lista separada por comas de comandos de shell adicionales para agregar a la whitelist. Ejemplo: `make,cargo,docker`. Nota: los comandos permanentemente bloqueados (`rm`, `sudo`, etc.) no pueden agregarse aquí. |
| `FORGE_TERMINAL_MAX_LINES` | `200` | Máximo de líneas de output retornadas de los comandos de terminal. El output más allá de este límite se trunca con una nota. |
| `FORGE_HTTP_TIMEOUT` | `15` | Segundos antes de que una petición HTTP (via tools de `internet/`) expire. |
| `FORGE_MAX_CONTENT_CHARS` | `12000` | Máximo de caracteres retornados de `fetch_url()` y `search_docs()`. El contenido más allá se trunca. |

---

## Logging

| Variable | Default | Descripción |
|----------|---------|-------------|
| `FORGE_LOG_MAX_MB` | `5` | Tamaño máximo de cada archivo de log antes de la rotación. Cuando se supera, el archivo se renombra a `.log.1` y comienza uno nuevo. |

---

## Modo desarrollador

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DEV_MODE` | `false` | Activar output de desarrollador. Muestra requests completos a la API, respuestas raw del LLM y eventos de compresión. También puede forzarse con `python app.py --dev`. |

---

## Ejemplo de `.env`

```env
# ── Requeridas ────────────────────────────────
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
FORGE_PROJECT_ROOT=/home/usuario/miproyecto

# ── LLM ──────────────────────────────────────
GROQ_MODEL=llama-3.3-70b-versatile
FORGE_LANGUAGE=Spanish
FORGE_CONTEXT_LIMIT=128000
FORGE_COMPRESS_AT=0.80

# ── Seguridad ────────────────────────────────
FORGE_SANDBOX=true
FORGE_EXEC_TIMEOUT=30
FORGE_ALLOWED_EXTENSIONS=.py,.js,.ts,.go,.rs,.rb,.java
FORGE_MAX_WRITE_BYTES=1048576

# ── Tools ────────────────────────────────────
FORGE_MAX_STEPS=20
FORGE_EXTRA_COMMANDS=
FORGE_TERMINAL_MAX_LINES=200
FORGE_HTTP_TIMEOUT=15
FORGE_MAX_CONTENT_CHARS=12000

# ── Logging ──────────────────────────────────
FORGE_LOG_MAX_MB=5

# ── Desarrollador ────────────────────────────
DEV_MODE=false
```

---

## Notas

**`FORGE_PROJECT_ROOT` es crítico.** Si está configurado incorrectamente, `guard_path()` bloqueará todas las operaciones de archivo porque los paths resueltos no coincidirán con la raíz esperada. Siempre usa la ruta absoluta.

**`FORGE_LANGUAGE` afecta los prompts, no el output de las tools.** Los resultados de las tools (contenido de archivos, output de git, resultados de pytest) se retornan tal cual. Solo el razonamiento del agente, los resúmenes y los reportes están en el idioma configurado.

**`DEV_MODE=true` no tiene impacto de rendimiento en uso de producción.** Las funciones `dev_log_request` y `dev_log_response` son no-ops cuando `DEV_MODE=false`. El único overhead es la verificación de la variable de entorno al importar el módulo.