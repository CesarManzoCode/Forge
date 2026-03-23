# Referencia de Módulos

Documentación detallada de cada módulo de Forge.

---

## `app.py`

**Punto de entrada.** Maneja el bootstrap y el parseo de argumentos.

**Responsabilidades:**
- Agrega la raíz del proyecto a `sys.path` para que todos los imports resuelvan correctamente independientemente de desde dónde se invoque el script
- Carga `.env` antes de cualquier módulo que lea variables de entorno al importarse
- Parsea argumentos CLI (flag `--dev`)
- Llama a `interface/cli/cli.py:main()`

**Argumentos:**
- `--dev` — Fuerza `DEV_MODE=true`, sobreescribiendo el valor del `.env`

**Uso:**
```bash
python app.py           # Modo normal
python app.py --dev     # Modo desarrollador
```

**Detalle clave:** `load_dotenv()` se llama aquí, antes de los imports de `llm/`, `tasks/`, o `src/`. Esto es intencional — `dev.py` lee `DEV_MODE` a nivel de módulo, entonces el env debe estar cargado antes de que cualquiera de esos módulos se importe.

---

## `llm/ai.py`

**Cliente de la API de Groq con gestión de context window.**

### Clase: `AI`

```python
AI(system_prompt: str = None)
```

**Constructor:** Inicializa el cliente Groq desde `GROQ_API_KEY`, establece el modelo desde `GROQ_MODEL`, y agrega el system prompt como primera entrada del historial.

**Métodos:**

```python
chat(message: str) -> str
```
Agrega `message` al historial, llama a `_maybe_compress()`, envía el historial completo a Groq, agrega la respuesta, retorna el string de respuesta raw.

```python
reset()
```
Limpia el historial pero preserva el system prompt. Usado entre subtareas para descartar las observaciones de ejecución mientras se mantiene la definición del rol del agente.

```python
inject_context(content: str, label: str = "context")
```
Agrega un par usuario/asistente al historial sin pasar por el flujo de chat. El mensaje de usuario contiene el contenido etiquetado; el asistente responde con "Understood." Usado para inyectar listas de tools, contexto del proyecto y preferencias del usuario.

```python
token_count() -> int
```
Retorna el conteo de tokens actual usando la codificación `cl100k_base` de tiktoken. Cae en estimación basada en caracteres (`chars // 4`) si tiktoken no está disponible.

```python
context_usage() -> dict
```
Retorna `{tokens, limit, threshold, percent, will_compress_at}`.

**Compresión de contexto (`_maybe_compress`):**

Se activa antes de cada llamada a la API si el conteo de tokens supera `FORGE_COMPRESS_AT * FORGE_CONTEXT_LIMIT` (por defecto: 80% de 128k = 102,400 tokens).

Estrategia de compresión:
1. Mantiene el system prompt intacto
2. Mantiene los últimos 4 pares usuario/asistente (el contexto más reciente)
3. Toma todos los mensajes del medio y los envía a una llamada de resumen separada
4. Reemplaza los mensajes del medio con una entrada `[HISTORY SUMMARY]`

La llamada de resumen usa `max_tokens=300` para producir un resumen técnico conciso.

**Variables de entorno:**
| Variable | Default | Descripción |
|----------|---------|-------------|
| `GROQ_API_KEY` | (requerido) | Clave API de Groq |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Modelo a usar |
| `FORGE_CONTEXT_LIMIT` | `128000` | Máximo de tokens del modelo |
| `FORGE_COMPRESS_AT` | `0.80` | Umbral de activación de compresión |

---

## `llm/prompts.py`

**Biblioteca centralizada de prompts.** Todos los prompts del LLM en un solo lugar.

**Constante a nivel de módulo:**
```python
LANGUAGE = os.getenv("FORGE_LANGUAGE", "English")
```
Leído una vez al importar. Usado en todos los prompts visibles al usuario.

### `SYSTEM`

El prompt principal de la personalidad de Forge. Define rasgos, capacidades e idioma. Usado como system prompt para el AI de chat en `cli.py`.

### `class Planner`

```python
Planner.generate(task_description: str) -> str
```
Prompt completo del planificador. Incluye reglas para la granularidad de subtareas, los ejemplos BAD/GOOD y el formato JSON exacto requerido.

```python
Planner.clarify(task_description: str, question: str) -> str
```
Usado cuando el planificador necesita hacer una pregunta de aclaración antes de generar un plan.

```python
Planner.replan(original_plan: str, feedback: str) -> str
```
Usado para revisar un plan existente basado en feedback del usuario.

### `class Executor`

```python
Executor.run_subtask(subtask: dict, project_context: str, task_context: str) -> str
```
El prompt enviado para iniciar cada subtarea en el loop ReAct. Incluye contexto del proyecto, resultados de subtareas anteriores y la descripción de la subtarea actual.

### `class Chat`

Constantes de strings para mensajes del sistema mostrados al usuario. No se envían al LLM.

---

## `llm/dev.py`

**Output del modo desarrollador.** Sin overhead cuando está desactivado.

**Constante a nivel de módulo:**
```python
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
```

**Funciones:**

```python
dev_log_request(model: str, messages: list[dict]) -> float
```
Imprime el bloque `[DEV:REQUEST]`. Trunca mensajes largos a 300 caracteres. Retorna `time.time()` para medir tiempo, incluso cuando el modo dev está apagado.

```python
dev_log_response(raw_response: str, start_time: float)
```
Imprime el bloque `[DEV:RESPONSE]`. Detecta JSON en la respuesta y lo imprime de forma legible. Muestra tiempo transcurrido y longitud de la respuesta.

---

## `interface/cli/cli.py`

**Interfaz de terminal completa.** ~450 líneas. Un solo archivo para todo el CLI.

### Helpers de display

Todas las funciones de display escriben directamente a stdout. Son sin estado — sin efectos secundarios más allá de imprimir.

| Función | Propósito |
|---------|-----------|
| `header()` | Limpia la terminal, imprime logo ASCII |
| `print_agent(text)` | Envuelve texto en caja `┌─ Forge ─` |
| `print_user_prompt()` | Imprime `┌─ You ─` y cursor |
| `print_plan(data)` | Formatea e imprime un plan de tarea |
| `print_help()` | Imprime referencia de comandos |
| `print_info/success/error(msg)` | Mensajes de estado |

`WIDTH = 64` controla todo el formateo. Cambia esta constante para ajustar el ancho del display.

### Funciones de comandos

| Función | Firma | Descripción |
|---------|-------|-------------|
| `cmd_task` | `(ai, active_executor)` | Abre editor de tareas, llama al planificador, guarda plan |
| `cmd_start` | `(ai, active_executor)` | Crea Executor, lo ejecuta, maneja eventos |
| `cmd_stop` | — | Establece flag de stop en executor activo |
| `cmd_status` | `(ai=None)` | Muestra estado de tarea y uso del contexto |
| `cmd_reset` | `(ai)` | Limpia historial AI, opcionalmente limpia tarea |
| `cmd_exit` | `()` | Limpia estado de sesión, llamado antes de salir |

### `InputListener`

Helper de threading que escucha comandos mientras el agente trabaja. Usa un hilo daemon con una cola protegida por `threading.Lock`. Actualmente no se usa en el flujo principal de chat (removido para prevenir conflictos con `input()`) pero se mantiene para uso futuro asíncrono del motor de ejecución.

### Loop principal

```python
def main():
    ai = AI(system_prompt=SYSTEM)
    active_executor = {"ref": None}

    while True:
        user_input = input()
        # despachar a funciones de comando o ai.chat()
```

`active_executor` es un dict mutable (no una variable simple) para que `cmd_start` pueda actualizarlo y el loop principal pueda verificarlo para `/stop`.

---

## `src/security/config.py`

**Reglas de seguridad.** Listas fijas y valores configurables.

### Reglas fijas (hardcodeadas, no sobreescribibles)

- `BLOCKED_ABSOLUTE` — prefijos de directorios del sistema
- `BLOCKED_FILENAMES` — nombres de archivo sensibles
- `BLOCKED_EXEC_EXTENSIONS` — extensiones que no pueden ejecutarse

### Reglas configurables (via `.env`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `FORGE_PROJECT_ROOT` | `os.getcwd()` | Raíz del árbol de archivos permitido |
| `FORGE_ALLOWED_EXTENSIONS` | `.py,.js,.ts,.go,.rs,.rb,.java` | Extensiones ejecutables |
| `FORGE_MAX_WRITE_BYTES` | `1048576` (1MB) | Máximo bytes por operación de escritura |
| `FORGE_SANDBOX` | `true` | Activar/desactivar sandbox de ejecución |
| `FORGE_EXEC_TIMEOUT` | `30` | Timeout de ejecución de código en segundos |

---

## `src/security/guards.py`

**Funciones de validación.** Llamadas por cada tool antes de cualquier operación de archivo o ejecución.

```python
guard_path(path: str, operation: str = "access") -> Path
```
Resuelve paths relativos contra `project_root`. Verifica contención, directorios bloqueados y nombres de archivo bloqueados. Retorna `Path` resuelto en éxito, lanza `SecurityError` en fallo.

```python
guard_write(path: str, content: str | bytes) -> Path
```
Llama a `guard_path` luego verifica el tamaño del contenido contra `max_write_bytes`.

```python
guard_exec(code: str, language: str) -> str
```
Valida el lenguaje contra extensiones permitidas. Ejecuta el código en un directorio temporal con el timeout configurado. Retorna stdout.

```python
@require_safe_path(arg_index=0, operation="read")
@require_safe_write(path_index=0, content_index=1)
```
Decoradores para aplicar guards a funciones de tools. La función decorada solo se ejecuta si el guard pasa.

**`SecurityError`** es una clase de excepción custom. Los llamadores (especialmente `react.py`) la capturan específicamente para distinguir bloqueos de seguridad de otros errores.

---

## `tasks/execution/registry.py`

**Registry de tools.** Mapea nombres de string a funciones Python para el agente.

```python
TOOLS: dict[str, dict]
```
Cada entrada tiene `fn`, `description` y `args` (schema con sufijo `?` para opcionales).

```python
class ToolRegistry:
    def call(self, tool_name: str, args: dict) -> str
    def tool_list(self) -> str
```

`call()` valida los args requeridos, maneja casos especiales para `git()` (usa `*args`) y `curl()`, luego normaliza el valor de retorno a string. Las listas y dicts se serializan a JSON.

`tool_list()` retorna un string formateado de todas las tools para inyección en el prompt del LLM.

---

## `tasks/execution/react.py`

**Implementación del loop ReAct.**

### Dataclass `Step`
```python
@dataclass
class Step:
    thought: str
    tool: str | None
    args: dict
    observation: str | None
    error: str | None
```

### Dataclass `ReactResult`
```python
@dataclass
class ReactResult:
    success: bool
    result: str
    steps: list[Step]
    steps_taken: int
```

### `ReactLoop`

```python
ReactLoop(ai: AI)
run(subtask, project_context, task_context) -> ReactResult
```

El loop corre hasta `FORGE_MAX_STEPS` (por defecto 20) iteraciones. Cada iteración:
1. Parsea la respuesta JSON del LLM
2. Si `done: true` → retorna `ReactResult(success=True)`
3. Si se propone una tool → ejecuta via `registry.call()`
4. Si hay error → retorna `ReactResult(success=False)`
5. Envía la observación de vuelta al LLM

Si el JSON es inválido, se intenta un retry con una solicitud de corrección explícita antes de abortar.

**Optimización del prompt de observación:** La primera observación incluye el recordatorio del formato JSON. Las siguientes son solo `[nombre_tool] resultado` — sin repetición.

---

## `tasks/execution/executor.py`

**Orquestador de subtareas.**

### `Executor`

```python
Executor(ai: AI)
run(on_update=None)
request_stop()
```

`run()` crea una instancia fresca `exec_ai = AI(system_prompt=_EXECUTION_SYSTEM)` para la ejecución. Esta es separada del AI de chat del CLI para prevenir contaminación del historial.

**Eventos del callback `on_update`:**
| Evento | Datos |
|--------|-------|
| `subtask_start` | dict de la subtarea |
| `subtask_done` | `{subtask, result, steps}` |
| `task_done` | dict de la tarea |
| `task_failed` | `{subtask, reason}` |
| `task_stopped` | `{message}` |

**Filtrado de tools (`_filter_tools`):**
Analiza la descripción de la subtarea por palabras clave de categoría. Siempre incluye tools de `file`. Agrega otras categorías (`code`, `terminal`, `internet`, `system`) si se encuentran palabras clave coincidentes en español o inglés.

---

## `logs/logger.py`

**Logging de tres canales con rotación.**

```python
logger = Logger()  # instancia global

logger.error(message, exc=None)
logger.crash(context, exc)
logger.task_done(task)
logger.task_failed(task, reason)
logger.agent_action(tool, args, result, subtask_id=None)
logger.agent_error(tool, args, error, subtask_id=None)
logger.info(message)
```

**Archivos de log:**
- `logs/errors.log` — errores y crashes con tracebacks
- `logs/tasks.log` — resúmenes de tareas completadas y mensajes info
- `logs/actions.log` — llamadas a tools con args y resultados

**Rotación:** Cuando un archivo de log supera `FORGE_LOG_MAX_MB` (por defecto 5MB), se renombra a `.log.1` y se crea un nuevo archivo vacío. Solo se mantiene un backup por tipo de archivo.