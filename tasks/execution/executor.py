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

TASK_FILE         = Path("tasks/project/task.json")
EXECUTION_DIR     = Path("tasks/execution")
CONTEXT_TASK_DIR  = Path("context/task")
CONTEXT_PROJECT_DIR = Path("context/project")


# ─────────────────────────────────────────────
#  EXECUTOR
# ─────────────────────────────────────────────

class Executor:

    def __init__(self, ai: AI):
        self.ai = ai
        self.react = ReactLoop(ai)
        self._on_update = None

    # ─────────────────────────────────────────
    #  PUBLIC
    # ─────────────────────────────────────────

    def run(self, on_update=None):
        """
        Ejecuta todas las subtasks pendientes en orden cronologico.

        Args:
            on_update: Callback opcional que recibe (event, data) en
                       cada cambio de estado. Usado por el CLI para
                       mostrar progreso en tiempo real.

                       Eventos posibles:
                         "subtask_start"   — data: subtask dict
                         "step"            — data: Step object
                         "subtask_done"    — data: {subtask, result}
                         "subtask_failed"  — data: {subtask, reason}
                         "task_done"       — data: task dict
                         "task_failed"     — data: {subtask, reason}
        """
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

        # Inyectar contexto del proyecto y preferencias del usuario al LLM
        self._inject_initial_context()

        # Inyectar el tool list al LLM una sola vez al inicio
        self.ai.inject_context(
            content=registry.tool_list(),
            label="AVAILABLE TOOLS"
        )

        # Ejecutar subtasks en orden
        for subtask in subtasks:
            if subtask["status"] == "done":
                continue  # ya completada en sesion anterior

            if subtask["status"] == "error":
                break     # habia fallado antes — no continuar

            # Verificar dependencias
            blocker = self._check_dependencies(subtask, subtasks)
            if blocker:
                self._fail_task(task, subtask, f"Dependency not met: subtask {blocker} is not done.")
                return

            # Marcar como in_progress
            subtask["status"] = "in_progress"
            self._save_task(task)
            self._emit("subtask_start", subtask)

            # Cargar contexto actual
            project_ctx = self._read_context(CONTEXT_PROJECT_DIR)
            task_ctx = self._read_context(CONTEXT_TASK_DIR)

            # Ejecutar el loop ReAct
            result: ReactResult = self.react.run(
                subtask=subtask,
                project_context=project_ctx,
                task_context=task_ctx,
            )

            if result.success:
                # Actualizar subtask
                subtask["status"] = "done"
                subtask["result"] = result.result
                subtask["completed_at"] = datetime.now().isoformat()
                subtask["steps_taken"] = result.steps_taken
                self._save_task(task)

                # Guardar resultado en context/task/ para subtasks siguientes
                self._write_task_context(subtask, result)

                self._emit("subtask_done", {
                    "subtask": subtask,
                    "result": result.result,
                    "steps": result.steps_taken,
                })

            else:
                # Fallo — parar todo
                subtask["status"] = "error"
                subtask["error"] = result.result
                subtask["failed_at"] = datetime.now().isoformat()
                self._fail_task(task, subtask, result.result)
                return

        # Todas las subtasks completadas
        task["status"] = "done"
        task["completed_at"] = datetime.now().isoformat()
        self._save_task(task)

        # Promover contexto de task a project
        self._promote_context()

        self._emit("task_done", task)

    # ─────────────────────────────────────────
    #  CONTEXT MANAGEMENT
    # ─────────────────────────────────────────

    def _inject_initial_context(self):
        """
        Inyecta al LLM el contexto del proyecto y las preferencias
        del usuario antes de empezar a ejecutar subtasks.
        """
        # Preferencias del usuario desde memory/
        memory_file = Path("memory/user.json")
        if memory_file.exists():
            try:
                prefs = json.loads(memory_file.read_text(encoding="utf-8"))
                flat = []
                for category, items in prefs.items():
                    for item in items:
                        flat.append(f"- [{category}] {item}")
                if flat:
                    self.ai.inject_context(
                        content="\n".join(flat),
                        label="USER PREFERENCES"
                    )
            except Exception:
                pass  # preferencias malformadas — ignorar silenciosamente

        # Contexto persistente del proyecto
        project_ctx = self._read_context(CONTEXT_PROJECT_DIR)
        if project_ctx:
            self.ai.inject_context(
                content=project_ctx,
                label="PROJECT CONTEXT"
            )

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