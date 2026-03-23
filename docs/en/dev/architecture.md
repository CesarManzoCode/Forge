# Architecture

Complete architectural overview of Forge.

---

## High-Level Design

Forge is a terminal AI agent built on a **ReAct loop** (Reason → Act → Observe). The user describes a task, the LLM plans it, and an execution engine runs each subtask using a controlled set of tools.

```
User Input
    │
    ▼
┌─────────────────────────────────────────────┐
│  interface/cli/cli.py                        │
│  CLI loop — input, commands, display         │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
┌─────────────┐  ┌──────────────────────────────┐
│ llm/ai.py   │  │ tasks/execution/executor.py   │
│ Groq API    │  │ Subtask orchestration         │
│ context mgmt│  └──────────────┬───────────────┘
└─────────────┘                 │
       ▲                        ▼
       │                ┌───────────────────────┐
       └────────────────│ tasks/execution/       │
                        │ react.py               │
                        │ ReAct loop per subtask │
                        └──────────┬────────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │ tasks/execution/      │
                        │ registry.py           │
                        │ Tool dispatcher       │
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

## Execution Flow

### Planning Phase

```
User types /task
      │
      ▼
cli.py → cmd_task()
      │
      ▼
ai.chat(Planner.generate(description))
      │
      ▼
LLM returns JSON plan
      │
      ▼
tasks/project/task.json saved
      │
      ▼
Plan displayed — waiting for /start
```

### Execution Phase

```
User types /start
      │
      ▼
cli.py → cmd_start() → Executor(ai)
      │
      ▼
executor.run()
      │
      ├── Creates fresh AI instance (exec_ai)
      │   with _EXECUTION_SYSTEM prompt
      │
      ├── Injects: user preferences, project context
      │
      └── For each subtask:
            │
            ├── Injects filtered tool list
            │
            ├── react.run(subtask, project_ctx, task_ctx)
            │       │
            │       ├── ai.chat(run_subtask prompt)
            │       │
            │       └── Loop:
            │               ├── Parse JSON response
            │               ├── Execute tool via registry
            │               ├── ai.chat(observation)
            │               └── Repeat until done/error
            │
            ├── Write result to context/task/
            │
            ├── exec_ai.reset()
            │
            └── Re-inject updated task context
```

---

## Key Design Decisions

### Separate AI instances for planning and execution

The CLI maintains one `AI` instance for general chat and task planning. When execution starts, `Executor` creates a **fresh** `AI` instance with a minimal system prompt. This prevents the planner's JSON history and chat messages from polluting the execution context, reducing token usage significantly.

### Context as files, not memory

Instead of keeping execution results in memory, Forge writes each subtask result to `context/task/*.md`. The next subtask reads these files at startup. This makes the context inspectable, debuggable, and persistent across process restarts.

### Tool filtering per subtask

Instead of injecting all 25+ tools into every subtask prompt, the executor analyzes the subtask description and injects only the relevant tool categories. This reduces prompt size and prevents the agent from choosing irrelevant tools.

### ReAct as a message loop

The ReAct pattern is implemented as a conversation loop with a single `AI` instance. Each `THINK→ACT→OBSERVE` cycle is a pair of messages: the agent responds with a tool call, the engine responds with the observation. This is simpler than a custom reasoning framework and leverages the LLM's conversational training.

### Security at the tool layer, not the prompt layer

Security is enforced in `src/security/guards.py`, not by telling the LLM what it's not allowed to do. Every tool call goes through guard functions regardless of what the prompt says. This means security cannot be bypassed by clever prompt manipulation.

---

## Directory Structure

```
Forge/
├── app.py                        Entry point, arg parsing, bootstrap
│
├── llm/
│   ├── ai.py                     Groq client, history management, context compression
│   ├── prompts.py                All LLM prompts in one place
│   └── dev.py                    Developer mode logging
│
├── interface/
│   └── cli/
│       └── cli.py                Full CLI: commands, display helpers, main loop
│
├── src/
│   ├── security/
│   │   ├── __init__.py           Public API: guard_path, guard_write, guard_exec
│   │   ├── config.py             Fixed and configurable security rules
│   │   └── guards.py             Validation functions and decorators
│   │
│   └── tools/
│       ├── file/__init__.py      read, write, patch, find, grep, tree
│       ├── code/__init__.py      run_file, run_code, run_tests, install_deps
│       ├── terminal/__init__.py  run_command, git, curl (whitelist enforced)
│       ├── internet/__init__.py  search_docs, fetch_url, fetch_github_raw
│       └── system/__init__.py    env_info, running_ports, disk_usage, get_env_var
│
├── tasks/
│   ├── project/
│   │   └── task.json             Current task state (generated at runtime)
│   └── execution/
│       ├── __init__.py
│       ├── registry.py           Maps tool names to functions + descriptions
│       ├── react.py              ReAct loop: Step, ReactResult, ReactLoop
│       └── executor.py           Orchestrator: subtask ordering, context flow
│
├── context/
│   ├── task/                     Subtask results (cleared on /exit)
│   └── project/                  Task summaries (cleared on /exit)
│
├── memory/
│   └── user.json                 Persistent user preferences
│
├── logs/
│   ├── errors.log                Crashes and exceptions
│   ├── tasks.log                 Task completion summaries
│   └── actions.log               Tool calls and results
│
└── docs/                         Documentation
```

---

## Data Flow: Context Between Subtasks

```
Subtask 1 completes
      │
      ▼
executor._write_task_context()
      │
      ▼
context/task/subtask_01_result.md
  - Description
  - Result summary
  - Key tool observations

Subtask 2 starts
      │
      ▼
executor._read_context(CONTEXT_TASK_DIR)
      │
      ▼
exec_ai.inject_context(task_ctx, "TASK CONTEXT")
      │
      ▼
LLM sees previous results before executing subtask 2

Task completes
      │
      ▼
executor._promote_context()
      │
      ▼
context/project/task_<title>.md  (summary of all subtasks)
context/task/ files deleted

/exit
      │
      ▼
context/task/ cleared
context/project/ cleared
tasks/project/task.json deleted
```

---

## Token Budget

For reference, approximate token costs per component with `llama-3.3-70b-versatile`:

| Component | Approximate tokens |
|-----------|-------------------|
| `_EXECUTION_SYSTEM` prompt | ~100 |
| Tool list (file category only) | ~400 |
| Tool list (all categories) | ~700 |
| Subtask description | ~50–150 |
| Task context (1 previous subtask) | ~200–400 |
| Project context (1 previous task) | ~150–300 |
| Each ReAct step (request + response) | ~300–600 |

The context window manager activates at 80% of the 128k token limit (~102k tokens) and compresses middle history into a ~300 token summary.