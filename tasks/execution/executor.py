"""
tasks/execution/executor.py — Orquestador del execution engine.

Lee task.json, ejecuta cada subtask en orden via ReactLoop,
actualiza el estado en tiempo real, y maneja el flujo de contexto
entre context/task/ y context/project/.

Uso desde cli.py:
    from tasks.execution.executor import Executor
    executor = Executor(ai)
    executor.run(on_update=callback)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from llm.ai import AI
from tasks.execution.react import ReactLoop, ReactResult
from tasks.execution.registry import registry


# ─────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────

TASK_FILE           = Path("tasks/project/task.json")
EXECUTION_DIR       = Path("tasks/execution")
CONTEXT_TASK_DIR    = Path("context/task")
CONTEXT_PROJECT_DIR = Path("context/project")

# System prompt minimo para la AI de ejecucion
# No necesita personalidad — solo comportamiento preciso
_EXECUTION_SYSTEM = """You are a code execution agent. You complete development subtasks using tools.
Rules:
- Use one tool at a time. Wait for the result before the next step.
- Respond ONLY with valid JSON. No prose, no markdown, no explanation outside JSON.
- When done: {"thought": "...", "done": true, "result": "concise summary"}
- When using a tool: {"thought": "...", "tool": "tool_name", "args": {...}}
- Stay focused on the current subtask only."""

# Palabras clave para filtrar tools relevantes por subtask
_TOOL_CATEGORIES = {
    "file": ["read_file", "read_lines", "write_file", "append_file",
             "patch_file", "create_dir", "delete_file", "delete_dir",
             "move", "find_files", "grep", "tree"],
    "code": ["run_file", "run_code", "run_tests", "install_deps", "check_env"],
    "terminal": ["run_command", "git", "curl", "whitelist_info"],
    "internet": ["search_docs", "fetch_url", "fetch_github_raw", "docs_sources"],
    "system":   ["env_info", "running_ports", "disk_usage", "get_env_var", "list_env_vars"],
}

_CATEGORY_KEYWORDS = {
    "file":     ["file", "read", "write", "create", "delete", "move",
                 "directory", "folder", "find", "search", "content", "path"],
    "code":     ["run", "execute", "test", "install", "python", "script",
                 "dependencies", "pytest", "pip", "code"],
    "terminal": ["git", "command", "terminal", "shell", "commit", "push",
                 "pull", "branch", "curl", "http", "request"],
    "internet": ["docs", "documentation", "search", "fetch", "github",
                 "api", "url", "web", "library"],
    "system":   ["environment", "version", "port", "disk", "env", "runtime",
                 "installed", "available", "system", "setup", "check"],
}


def _filter_tools(subtask_description: str) -> str:
    """
    Retorna solo las tools relevantes para esta subtask.
    Siempre incluye file tools como base — son las mas usadas.
    Agrega otras categorias si la descripcion contiene palabras clave.
    """
    desc = subtask_description.lower()
    active_categories = {"file"}  # siempre incluir file

    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in desc for kw in keywords):
            active_categories.add(category)

    relevant_tools = []
    for category in active_categories:
        relevant_tools.extend(_TOOL_CATEGORIES[category])

    lines = []
    for name, tool in registry.TOOLS.items():
        if name not in relevant_tools:
            continue
        args_str = ", ".join(f"{k}: {v}" for k, v in tool["args"].items())
        lines.append(f"- {name}({args_str}): {tool['description']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
#  EXECUTOR
# ─────────────────────────────────────────────

class Executor:

    def __init__(self, ai: AI):
        self.ai = ai
        self.react = ReactLoop(ai)
        self._on_update = None
        self._stop_requested = False

    def request_stop(self):
        """Señal para detener la ejecucion al terminar la subtask actual."""
        self._stop_requested = True

    # ─────────────────────────────────────────
    #  PUBLIC
    # ─────────────────────────────────────────

    def run(self, on_update=None):
        self._on_update = on_update

        task = self._load_task()
        if not task:
            raise FileNotFoundError(
                f"No task file found at '{TASK_FILE}'. "
                f"Run /task to create one."
            )

        subtasks = task.get("subtasks", [])
        if not subtasks:
            raise ValueError("Task has no subtasks.")

        # ── Crear AI limpia solo para ejecucion ──
        # No contaminar con historial de chat, "hola", el plan, etc.
        exec_ai = AI(system_prompt=_EXECUTION_SYSTEM)
        self.react = ReactLoop(exec_ai)

        # Inyectar contexto relevante una sola vez
        self._inject_initial_context(exec_ai)

        # Tool list se inyecta por subtask segun relevancia — no aqui

        for subtask in subtasks:
            if subtask["status"] == "done":
                continue
            if subtask["status"] == "error":
                break

            blocker = self._check_dependencies(subtask, subtasks)
            if blocker:
                self._fail_task(task, subtask, f"Dependency not met: subtask {blocker} is not done.")
                return

            subtask["status"] = "in_progress"
            self._save_task(task)
            self._emit("subtask_start", subtask)

            project_ctx = self._read_context(CONTEXT_PROJECT_DIR)
            task_ctx    = self._read_context(CONTEXT_TASK_DIR)

            # Inyectar solo las tools relevantes para esta subtask
            tools_for_subtask = _filter_tools(subtask["description"])
            exec_ai.inject_context(tools_for_subtask, label="AVAILABLE TOOLS")

            result: ReactResult = self.react.run(
                subtask=subtask,
                project_context=project_ctx,
                task_context=task_ctx,
            )

            if result.success:
                subtask["status"]       = "done"
                subtask["result"]       = result.result
                subtask["completed_at"] = datetime.now().isoformat()
                subtask["steps_taken"]  = result.steps_taken
                self._save_task(task)
                self._write_task_context(subtask, result)
                self._emit("subtask_done", {
                    "subtask": subtask,
                    "result":  result.result,
                    "steps":   result.steps_taken,
                })

                # Reset AI entre subtasks
                exec_ai.reset()

                # Verificar si el usuario pidio stop
                if self._stop_requested:
                    task["status"] = "paused"
                    self._save_task(task)
                    self._emit("task_stopped", {
                        "message": "Execution paused by user. Type /start to resume."
                    })
                    return

                # Re-inyectar contexto actualizado
                updated_ctx = self._read_context(CONTEXT_TASK_DIR)
                if updated_ctx:
                    exec_ai.inject_context(updated_ctx, label="TASK CONTEXT")

            else:
                subtask["status"]    = "error"
                subtask["error"]     = result.result
                subtask["failed_at"] = datetime.now().isoformat()
                self._fail_task(task, subtask, result.result)
                return

        task["status"]       = "done"
        task["completed_at"] = datetime.now().isoformat()
        self._save_task(task)
        self._promote_context()
        self._emit("task_done", task)

    # ─────────────────────────────────────────
    #  CONTEXT MANAGEMENT
    # ─────────────────────────────────────────

    def _inject_initial_context(self, ai: AI):
        """Inyecta preferencias del usuario y contexto del proyecto."""
        memory_file = Path("memory/user.json")
        if memory_file.exists():
            try:
                prefs = json.loads(memory_file.read_text(encoding="utf-8"))
                flat = [
                    f"- [{cat}] {item}"
                    for cat, items in prefs.items()
                    for item in items
                ]
                if flat:
                    ai.inject_context("\n".join(flat), label="USER PREFERENCES")
            except Exception:
                pass

        project_ctx = self._read_context(CONTEXT_PROJECT_DIR)
        if project_ctx:
            ai.inject_context(project_ctx, label="PROJECT CONTEXT")

    def _read_context(self, directory: Path) -> str:
        """
        Lee todos los archivos de un directorio de contexto
        y los combina en un solo string para el LLM.
        """
        if not directory.exists():
            return ""

        parts = []
        for f in sorted(directory.iterdir()):
            if f.is_file():
                try:
                    content = f.read_text(encoding="utf-8").strip()
                    if content:
                        parts.append(f"### {f.name}\n{content}")
                except Exception:
                    continue

        return "\n\n".join(parts)

    def _write_task_context(self, subtask: dict, result: ReactResult):
        """
        Guarda el resultado de una subtask en context/task/.
        Las subtasks siguientes lo leeran como contexto.
        """
        CONTEXT_TASK_DIR.mkdir(parents=True, exist_ok=True)

        filename = f"subtask_{subtask['id']:02d}_result.md"
        content = (
            f"# Subtask {subtask['id']}: {subtask['description']}\n\n"
            f"**Status:** done\n"
            f"**Steps taken:** {result.steps_taken}\n\n"
            f"## Result\n{result.result}\n\n"
        )

        # Agregar observaciones relevantes de los pasos
        observations = [
            s for s in result.steps
            if s.observation and len(s.observation) < 2000
        ]
        if observations:
            content += "## Key observations\n"
            for step in observations[-3:]:  # solo los ultimos 3 para no saturar
                content += f"- **{step.tool}**: {step.observation[:300]}...\n" \
                    if len(step.observation) > 300 \
                    else f"- **{step.tool}**: {step.observation}\n"

        (CONTEXT_TASK_DIR / filename).write_text(content, encoding="utf-8")

        # Registrar en subtask cuales archivos escribio
        subtask["context_written"].append(f"context/task/{filename}")

    def _promote_context(self):
        """
        Al completar la tarea, mueve el resumen de context/task/
        a context/project/ para que persista en futuras tareas.
        """
        task = self._load_task()
        if not task:
            return

        CONTEXT_PROJECT_DIR.mkdir(parents=True, exist_ok=True)

        summary_file = CONTEXT_PROJECT_DIR / f"task_{task.get('title', 'task').replace(' ', '_')[:40]}.md"

        lines = [
            f"# Completed task: {task.get('title', 'Untitled')}\n",
            f"Date: {task.get('completed_at', 'unknown')}\n\n",
            "## Subtasks completed\n",
        ]
        for st in task.get("subtasks", []):
            lines.append(f"- [{st['id']}] {st['description']}: {st.get('result', '')[:120]}\n")

        summary_file.write_text("".join(lines), encoding="utf-8")

        # Limpiar context/task/ — ya no es necesario
        if CONTEXT_TASK_DIR.exists():
            for f in CONTEXT_TASK_DIR.iterdir():
                if f.is_file():
                    f.unlink()

    # ─────────────────────────────────────────
    #  TASK FILE
    # ─────────────────────────────────────────

    def _load_task(self) -> dict | None:
        if not TASK_FILE.exists():
            return None
        return json.loads(TASK_FILE.read_text(encoding="utf-8"))

    def _save_task(self, task: dict):
        TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASK_FILE.write_text(
            json.dumps(task, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def _fail_task(self, task: dict, subtask: dict, reason: str):
        task["status"] = "error"
        task["failed_at"] = datetime.now().isoformat()
        self._save_task(task)
        self._emit("task_failed", {"subtask": subtask, "reason": reason})

    def _check_dependencies(self, subtask: dict, all_subtasks: list) -> int | None:
        """
        Verifica que todas las dependencias de una subtask esten completadas.
        Retorna el id de la primera dependencia no completada, o None si todo ok.
        """
        done_ids = {
            st["id"] for st in all_subtasks
            if st["status"] == "done"
        }
        for dep_id in subtask.get("depends_on", []):
            if dep_id not in done_ids:
                return dep_id
        return None

    # ─────────────────────────────────────────
    #  EVENTS
    # ─────────────────────────────────────────

    def _emit(self, event: str, data):
        if self._on_update:
            try:
                self._on_update(event, data)
            except Exception:
                pass  # el callback no debe romper la ejecucion