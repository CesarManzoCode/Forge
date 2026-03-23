# Arquitectura

Visión arquitectónica completa de Forge.

---

## Diseño de alto nivel

Forge es un agente de IA para la terminal construido sobre un **loop ReAct** (Razonar → Actuar → Observar). El usuario describe una tarea, el LLM la planifica, y un motor de ejecución ejecuta cada subtarea usando un conjunto controlado de herramientas.

```
Entrada del usuario
    │
    ▼
┌─────────────────────────────────────────────┐
│  interface/cli/cli.py                        │
│  Loop del CLI — entrada, comandos, display   │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
┌─────────────┐  ┌──────────────────────────────┐
│ llm/ai.py   │  │ tasks/execution/executor.py   │
│ API Groq    │  │ Orquestación de subtareas     │
│ gestión ctx │  └──────────────┬───────────────┘
└─────────────┘                 │
       ▲                        ▼
       │                ┌───────────────────────┐
       └────────────────│ tasks/execution/       │
                        │ react.py               │
                        │ Loop ReAct por subtarea│
                        └──────────┬────────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │ tasks/execution/      │
                        │ registry.py           │
                        │ Despachador de tools  │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼               ▼
              src/tools/      src/tools/      src/tools/
               file/           code/          terminal/
                                               internet/
                                               system/
                    │
                    ▼
              src/security/
              guards.py
```

---

## Flujo de ejecución

### Fase de planificación

```
Usuario escribe /task
      │
      ▼
cli.py → cmd_task()
      │
      ▼
ai.chat(Planner.generate(descripcion))
      │
      ▼
LLM retorna JSON del plan
      │
      ▼
tasks/project/task.json guardado
      │
      ▼
Plan mostrado — esperando /start
```

### Fase de ejecución

```
Usuario escribe /start
      │
      ▼
cli.py → cmd_start() → Executor(ai)
      │
      ▼
executor.run()
      │
      ├── Crea instancia AI limpia (exec_ai)
      │   con prompt _EXECUTION_SYSTEM
      │
      ├── Inyecta: preferencias usuario, contexto proyecto
      │
      └── Por cada subtarea:
            │
            ├── Inyecta lista de tools filtrada
            │
            ├── react.run(subtarea, ctx_proyecto, ctx_tarea)
            │       │
            │       ├── ai.chat(prompt run_subtask)
            │       │
            │       └── Loop:
            │               ├── Parsear respuesta JSON
            │               ├── Ejecutar tool via registry
            │               ├── ai.chat(observación)
            │               └── Repetir hasta done/error
            │
            ├── Escribir resultado en context/task/
            │
            ├── exec_ai.reset()
            │
            └── Re-inyectar contexto de tarea actualizado
```

---

## Decisiones de diseño clave

### Instancias AI separadas para planificación y ejecución

El CLI mantiene una instancia `AI` para chat general y planificación. Cuando comienza la ejecución, el `Executor` crea una instancia `AI` **limpia** con un system prompt mínimo. Esto evita que el historial JSON del planificador y los mensajes de chat contaminen el contexto de ejecución, reduciendo significativamente el uso de tokens.

### El contexto como archivos, no como memoria

En lugar de mantener los resultados de ejecución en memoria, Forge escribe el resultado de cada subtarea en `context/task/*.md`. La siguiente subtarea lee estos archivos al iniciar. Esto hace el contexto inspeccionable, debuggeable y persistente ante reinicios del proceso.

### Filtrado de tools por subtarea

En lugar de inyectar todas las 25+ tools en cada prompt de subtarea, el executor analiza la descripción de la subtarea e inyecta solo las categorías de tools relevantes. Esto reduce el tamaño del prompt y evita que el agente elija tools irrelevantes.

### ReAct como loop de mensajes

El patrón ReAct está implementado como un loop de conversación con una sola instancia `AI`. Cada ciclo `PENSAR→ACTUAR→OBSERVAR` es un par de mensajes: el agente responde con una llamada a una tool, el motor responde con la observación. Esto es más simple que un framework de razonamiento custom y aprovecha el entrenamiento conversacional del LLM.

### Seguridad en la capa de tools, no en el prompt

La seguridad se aplica en `src/security/guards.py`, no diciéndole al LLM qué no puede hacer. Toda llamada a una tool pasa por funciones de validación independientemente de lo que diga el prompt. Esto significa que la seguridad no puede ser esquivada por manipulación del prompt.

---

## Estructura de directorios

```
Forge/
├── app.py                        Punto de entrada, parseo de args, bootstrap
│
├── llm/
│   ├── ai.py                     Cliente Groq, gestión de historial, compresión de contexto
│   ├── prompts.py                Todos los prompts LLM en un solo lugar
│   └── dev.py                    Logging del modo desarrollador
│
├── interface/
│   └── cli/
│       └── cli.py                CLI completo: comandos, helpers de display, loop principal
│
├── src/
│   ├── security/
│   │   ├── __init__.py           API pública: guard_path, guard_write, guard_exec
│   │   ├── config.py             Reglas fijas y configurables de seguridad
│   │   └── guards.py             Funciones de validación y decoradores
│   │
│   └── tools/
│       ├── file/__init__.py      read, write, patch, find, grep, tree
│       ├── code/__init__.py      run_file, run_code, run_tests, install_deps
│       ├── terminal/__init__.py  run_command, git, curl (whitelist aplicada)
│       ├── internet/__init__.py  search_docs, fetch_url, fetch_github_raw
│       └── system/__init__.py    env_info, running_ports, disk_usage, get_env_var
│
├── tasks/
│   ├── project/
│   │   └── task.json             Estado actual de la tarea (generado en runtime)
│   └── execution/
│       ├── __init__.py
│       ├── registry.py           Mapea nombres de tools a funciones + descripciones
│       ├── react.py              Loop ReAct: Step, ReactResult, ReactLoop
│       └── executor.py           Orquestador: orden de subtareas, flujo de contexto
│
├── context/
│   ├── task/                     Resultados de subtareas (limpiado en /exit)
│   └── project/                  Resúmenes de tareas (limpiado en /exit)
│
├── memory/
│   └── user.json                 Preferencias persistentes del usuario
│
├── logs/
│   ├── errors.log                Crashes y excepciones
│   ├── tasks.log                 Resúmenes de tareas completadas
│   └── actions.log               Llamadas a tools y resultados
│
└── docs/                         Documentación
```

---

## Flujo de datos: contexto entre subtareas

```
Subtarea 1 completa
      │
      ▼
executor._write_task_context()
      │
      ▼
context/task/subtask_01_result.md
  - Descripción
  - Resumen del resultado
  - Observaciones clave de las tools

Subtarea 2 inicia
      │
      ▼
executor._read_context(CONTEXT_TASK_DIR)
      │
      ▼
exec_ai.inject_context(ctx_tarea, "TASK CONTEXT")
      │
      ▼
LLM ve resultados anteriores antes de ejecutar subtarea 2

Tarea completa
      │
      ▼
executor._promote_context()
      │
      ▼
context/project/task_<titulo>.md  (resumen de todas las subtareas)
archivos context/task/ eliminados

/exit
      │
      ▼
context/task/ limpiado
context/project/ limpiado
tasks/project/task.json eliminado
```

---

## Presupuesto de tokens

Costos aproximados en tokens por componente con `llama-3.3-70b-versatile`:

| Componente | Tokens aproximados |
|-----------|-------------------|
| Prompt `_EXECUTION_SYSTEM` | ~100 |
| Lista de tools (solo categoría file) | ~400 |
| Lista de tools (todas las categorías) | ~700 |
| Descripción de subtarea | ~50–150 |
| Contexto de tarea (1 subtarea anterior) | ~200–400 |
| Contexto de proyecto (1 tarea anterior) | ~150–300 |
| Cada paso ReAct (request + response) | ~300–600 |

El gestor de context window se activa al 80% del límite de 128k tokens (~102k tokens) y comprime el historial intermedio en un resumen de ~300 tokens.