# Capacidades

Qué puede y qué no puede hacer Forge.

---

## Lo que Forge puede hacer

### Operaciones de archivo

Forge puede leer, escribir y modificar archivos dentro del directorio de tu proyecto.

- Leer cualquier archivo completo o por rango de líneas
- Crear nuevos archivos y directorios
- Escribir y sobreescribir archivos
- Parchear secciones específicas de un archivo sin reescribirlo completo
- Buscar archivos por patrón de nombre (`*.py`, `test_*.py`, `**/*.json`)
- Buscar texto dentro de archivos (como `grep`)
- Mostrar la estructura de directorios

**Ejemplos de tareas:**
- "Crea un archivo `config.py` con estas configuraciones..."
- "Lee `src/auth.py` y refactoriza la función de login para usar JWT"
- "Encuentra todos los archivos Python que importan `os.path` y listarlos"

---

### Ejecución de código

Forge puede ejecutar código Python dentro de tu proyecto.

- Ejecutar archivos Python existentes
- Correr snippets de Python en un entorno sandboxed
- Correr suites de tests con pytest con output completo
- Instalar paquetes Python con pip

Toda la ejecución de código ocurre dentro de un sandbox — un directorio temporal aislado del resto del sistema.

**Ejemplos de tareas:**
- "Ejecuta `src/main.py` y muéstrame el output"
- "Escribe tests para `math_utils.py` y córrelos"
- "Instala `requests` y `pytest`"

---

### Comandos de terminal

Forge puede ejecutar un conjunto controlado de comandos de shell.

**Operaciones de git:** `status`, `log`, `diff`, `add`, `commit`, `branch`, `checkout`, `stash`, `push`, `pull`, `fetch`, `init`, `clone`, `merge`, `rebase`, `tag`, `blame`, `rev-parse`

**Peticiones HTTP:** `curl` y `wget` con cualquier flag

**Comandos adicionales:** Puedes agregar más comandos a la whitelist via `FORGE_EXTRA_COMMANDS` en `.env`

**Ejemplos de tareas:**
- "Verifica el estado de git y muéstrame los últimos 5 commits"
- "Agrega todos los archivos modificados y haz commit con el mensaje `fix: actualizar lógica de auth`"
- "Obtén la respuesta de `https://api.ejemplo.com/usuarios`"

---

### Búsqueda de documentación

Forge puede buscar y leer documentación técnica.

| Fuente | Qué cubre |
|--------|-----------|
| `python` | Documentación oficial de Python 3 |
| `mdn` | JavaScript, HTML, CSS, Web APIs |
| `nodejs` | Documentación oficial de Node.js |
| `rust` | Librería estándar de Rust |
| `pypi` | Índice de paquetes Python |
| `github` | Búsqueda de repositorios en GitHub |

Forge también puede obtener cualquier URL y leerla como texto limpio, y leer archivos raw directamente de repositorios GitHub.

**Ejemplos de tareas:**
- "Busca en la documentación de Python sobre `asyncio.gather` y explica cómo usarlo"
- "Lee el README de `github.com/psf/requests` y resume la instalación"

---

### Información del sistema

Forge puede inspeccionar el entorno de desarrollo.

- Versiones de runtimes instalados (Python, Node, Go, Rust, Java)
- Herramientas de desarrollo disponibles (git, docker, pytest, ruff, black)
- Uso de disco
- Qué puertos están en uso
- Variables de entorno (solo las no sensibles)

**Ejemplos de tareas:**
- "Verifica si pytest está instalado y qué versión tiene"
- "¿El puerto 8000 está en uso?"
- "¿Cuánto espacio libre hay en el directorio del proyecto?"

---

## Lo que Forge no puede hacer

### Fuera del directorio del proyecto

Forge está estrictamente confinado a `FORGE_PROJECT_ROOT`. No puede:

- Leer, escribir o eliminar archivos fuera del proyecto
- Acceder a directorios del sistema (`/etc`, `/usr`, `/root`, etc.)
- Leer o modificar `.env`, `.ssh` u otros archivos sensibles

Esto se aplica en la capa de seguridad y no puede anularse desde la descripción de una tarea.

### Operaciones destructivas sin confirmación

Forge requiere `confirmed=True` explícito para eliminar archivos o directorios. El agente no puede auto-autorizarse — debes aprobarlo cuando el agente lo solicite.

### Scripts de shell

Ejecutar archivos `.sh`, `.bash` o `.zsh` directamente está bloqueado. Usa `tools/terminal` para comandos de shell o `tools/code` para scripts Python.

### Comandos de shell arbitrarios

Solo los comandos en la whitelist pueden ejecutarse. Comandos como `rm`, `sudo`, `chmod`, `systemctl` y otros están permanentemente bloqueados sin importar la descripción de la tarea.

### Acceso a tus secretos

Las claves API, contraseñas, tokens y otras variables de entorno sensibles están permanentemente bloqueadas para el agente. El agente nunca puede leer `GROQ_API_KEY`, `DATABASE_URL` ni ninguna variable que coincida con patrones de secretos conocidos.

### Ejecución paralela

Forge ejecuta subtareas secuencialmente. No puede ejecutar múltiples subtareas al mismo tiempo.

---

## Limitaciones a tener en cuenta

**Context window:** Forge usa un LLM con un contexto de 128k tokens. Para sesiones muy largas, el gestor de contexto comprime automáticamente el historial antiguo en un resumen. Esto es transparente pero puede ocasionalmente hacer que el agente pierda detalles finos del inicio de la sesión.

**Precisión del planificador:** La calidad del plan depende de qué tan claramente describes la tarea. Las descripciones vagas producen planes vagos. Si el plan no se ve correcto, escribe `/task` de nuevo con una descripción más detallada.

**Dependencia del modelo:** La calidad del razonamiento de Forge depende del modelo LLM configurado en `GROQ_MODEL`. El modelo recomendado es `llama-3.3-70b-versatile`. Los modelos más pequeños (como `llama-3.1-8b-instant`) pueden producir JSON incorrecto o hacer elecciones de herramientas pobres.