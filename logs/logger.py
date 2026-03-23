"""
logs/logger.py — Sistema de logs de Forge.

Tres tipos de log, cada uno en su archivo:
  - errors.log    : crashes y excepciones
  - tasks.log     : resumen de tareas completadas
  - actions.log   : tools usadas por el agente

Limite por tamaño — cuando un archivo supera MAX_MB
se rota: se renombra a .1 y se crea uno nuevo.
Se mantiene solo 1 backup por archivo.

Uso:
    from logs.logger import logger
    logger.error("Something crashed", exc_info=True)
    logger.task_done(task)
    logger.agent_action("write_file", {"path": "hello.py"}, "Written 42 chars")
"""

import os
import json
import traceback
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

LOGS_DIR = Path("logs")
MAX_MB   = float(os.getenv("FORGE_LOG_MAX_MB", "5"))
MAX_BYTES = int(MAX_MB * 1024 * 1024)


# ─────────────────────────────────────────────
#  ROTATION
# ─────────────────────────────────────────────

def _rotate_if_needed(path: Path):
    """
    Si el archivo supera MAX_BYTES lo rota.
    archivo.log → archivo.log.1 (sobreescribe si ya existe)
    Luego crea un archivo.log nuevo vacio.
    """
    if not path.exists():
        return
    if path.stat().st_size < MAX_BYTES:
        return

    backup = path.with_suffix(path.suffix + ".1")
    path.rename(backup)


def _write(path: Path, entry: str):
    """Rota si necesario y escribe la entrada."""
    LOGS_DIR.mkdir(exist_ok=True)
    _rotate_if_needed(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────
#  LOGGER
# ─────────────────────────────────────────────

class Logger:

    def __init__(self):
        self.errors_path  = LOGS_DIR / "errors.log"
        self.tasks_path   = LOGS_DIR / "tasks.log"
        self.actions_path = LOGS_DIR / "actions.log"

    # ── ERRORS ──

    def error(self, message: str, exc: Exception = None):
        """
        Registra un error del sistema.

        Args:
            message: Descripcion del error
            exc:     Excepcion opcional para incluir el traceback
        """
        lines = [f"[{_ts()}] ERROR — {message}"]
        if exc:
            tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
            lines.append("  " + "  ".join(tb))
        lines.append("")
        _write(self.errors_path, "\n".join(lines))

    def crash(self, context: str, exc: Exception):
        """
        Registra un crash inesperado con contexto completo.
        Llama esto desde los except generales del CLI.
        """
        lines = [
            f"[{_ts()}] CRASH in {context}",
            f"  {type(exc).__name__}: {exc}",
            "  " + "  ".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            "",
        ]
        _write(self.errors_path, "\n".join(lines))

    # ── TASKS ──

    def task_done(self, task: dict):
        """
        Registra el resumen de una tarea completada.

        Args:
            task: El dict completo de task.json
        """
        subtasks = task.get("subtasks", [])
        done     = sum(1 for s in subtasks if s["status"] == "done")
        failed   = sum(1 for s in subtasks if s["status"] == "error")

        lines = [
            f"[{_ts()}] TASK DONE — {task.get('title', 'Untitled')}",
            f"  status    : {task.get('status')}",
            f"  subtasks  : {done} done / {failed} failed / {len(subtasks)} total",
            f"  started   : {task.get('started_at', 'unknown')}",
            f"  completed : {task.get('completed_at', 'unknown')}",
        ]
        for st in subtasks:
            icon = "✓" if st["status"] == "done" else "✗"
            result = st.get("result") or st.get("error") or ""
            lines.append(f"  {icon} [{st['id']}] {st['description']}")
            if result:
                lines.append(f"      → {str(result)[:120]}")
        lines.append("")

        _write(self.tasks_path, "\n".join(lines))

    def task_failed(self, task: dict, reason: str):
        """Registra una tarea que fallo durante ejecucion."""
        lines = [
            f"[{_ts()}] TASK FAILED — {task.get('title', 'Untitled')}",
            f"  reason : {reason}",
            f"  status : {task.get('status')}",
            "",
        ]
        _write(self.tasks_path, "\n".join(lines))

    # ── ACTIONS ──

    def agent_action(self, tool: str, args: dict, result: str, subtask_id: int = None):
        """
        Registra una accion del agente — tool usada y resultado.

        Args:
            tool:        Nombre de la tool
            args:        Argumentos pasados
            result:      Output de la tool (truncado a 200 chars)
            subtask_id:  ID de la subtask activa
        """
        args_str   = json.dumps(args, ensure_ascii=False)
        result_str = str(result)[:200] + ("..." if len(str(result)) > 200 else "")
        subtask    = f"[subtask {subtask_id}] " if subtask_id else ""

        lines = [
            f"[{_ts()}] ACTION {subtask}— {tool}",
            f"  args   : {args_str}",
            f"  result : {result_str}",
            "",
        ]
        _write(self.actions_path, "\n".join(lines))

    def agent_error(self, tool: str, args: dict, error: str, subtask_id: int = None):
        """Registra una accion del agente que resulto en error."""
        args_str   = json.dumps(args, ensure_ascii=False)
        subtask    = f"[subtask {subtask_id}] " if subtask_id else ""

        lines = [
            f"[{_ts()}] ACTION ERROR {subtask}— {tool}",
            f"  args  : {args_str}",
            f"  error : {error}",
            "",
        ]
        _write(self.actions_path, "\n".join(lines))

    # ── INFO ──

    def info(self, message: str):
        """Log general — eventos de sistema no criticos."""
        _write(self.tasks_path, f"[{_ts()}] INFO — {message}\n")


# Instancia global
logger = Logger()