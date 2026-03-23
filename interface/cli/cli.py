import threading
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from llm.ai import AI
from llm.prompts import SYSTEM, Planner, Chat
from logs.logger import logger

# ─────────────────────────────────────────────
#  DISPLAY HELPERS
# ─────────────────────────────────────────────

WIDTH = 64

def line(char="─", width=WIDTH):
    print(char * width)

def header():
    os.system("clear" if os.name != "nt" else "cls")
    sys.stdout.flush()
    print("═" * WIDTH)
    print("  ███████╗ ██████╗ ██████╗  ██████╗ ███████╗")
    print("  ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝")
    print("  █████╗  ██║   ██║██████╔╝██║  ███╗█████╗  ")
    print("  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  ")
    print("  ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗")
    print("  ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝")
    print("═" * WIDTH)
    print(f"  AI Agent for Developers  ·  {datetime.now().strftime('%Y-%m-%d')}")
    print("═" * WIDTH)
    print()

def print_agent(text: str):
    print()
    print("┌─ Forge " + "─" * (WIDTH - 9))
    for paragraph in text.strip().split("\n"):
        print(f"│  {paragraph}")
    print("└" + "─" * (WIDTH - 1))
    print()

def print_user_prompt():
    print("┌─ You " + "─" * (WIDTH - 8))
    sys.stdout.write("│  > ")
    sys.stdout.flush()

def print_info(msg: str):
    print(f"\n  ·  {msg}")

def print_success(msg: str):
    print(f"\n  ✓  {msg}")

def print_error(msg: str):
    print(f"\n  ✗  {msg}")

def print_section(title: str):
    print()
    print(f"  ── {title} " + "─" * max(0, WIDTH - len(title) - 6))

def print_help():
    print()
    print("═" * WIDTH)
    print("  COMMANDS")
    print("─" * WIDTH)
    print("  /task     Describe a new task for Forge to plan")
    print("  /start    Execute the current plan")
    print("  /stop     Pause execution after current subtask")
    print("  /status   Show subtask execution progress")
    print("  /reset    Clear conversation history")
    print("  /help     Show this menu")
    print("  /exit     Exit Forge")
    print("═" * WIDTH)
    print()

def print_plan(data: dict):
    risk_icons = {"low": "○", "medium": "◐", "high": "●"}
    risk = data.get("risk_level", "unknown")
    icon = risk_icons.get(risk, "?")

    print()
    print("═" * WIDTH)
    print(f"  PLAN  ·  {data.get('title', 'Untitled')}")
    print("─" * WIDTH)
    print(f"  Risk      {icon}  {risk.upper()}")
    print(f"  Subtasks  {data.get('estimated_subtasks', len(data.get('subtasks', [])))}")
    print("─" * WIDTH)

    for st in data.get("subtasks", []):
        deps = f"  → after {st['depends_on']}" if st["depends_on"] else ""
        print(f"  {st['id']:>2}.  {st['description']}{deps}")

    print("─" * WIDTH)
    print(f"  {Chat.PLAN_READY}")
    print("═" * WIDTH)
    print()


# ─────────────────────────────────────────────
#  TASK STATE
# ─────────────────────────────────────────────

TASK_FILE = "tasks/project/task.json"
EXECUTION_DIR = "tasks/execution"


def load_task_file() -> dict | None:
    if not os.path.exists(TASK_FILE):
        return None
    try:
        content = open(TASK_FILE).read().strip()
        if not content:
            return None
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def save_task_file(data: dict):
    os.makedirs(os.path.dirname(TASK_FILE), exist_ok=True)
    with open(TASK_FILE, "w") as f:
        json.dump(data, f, indent=2)


def task_status() -> str:
    data = load_task_file()
    if not data:
        return "none"
    return data.get("status", "none")


# ─────────────────────────────────────────────
#  COMMANDS
# ─────────────────────────────────────────────

def cmd_task(ai: AI):
    status = task_status()

    if status == "running":
        print_agent(Chat.TASK_ALREADY_RUNNING)
        return

    if status in ("planned", "error", "done", "paused"):
        print_section("OVERWRITE EXISTING TASK")
        print(f"  There is already a task with status: {status}")
        sys.stdout.write("  Overwrite it? (y/N) > ")
        sys.stdout.flush()
        confirm = input().strip().lower()
        if confirm != "y":
            print_info("Cancelled.")
            return

    print_section("NEW TASK")
    print("  Describe the task in detail.")
    print("  Type END on a new line when done.")
    print()

    lines = []
    while True:
        sys.stdout.write("  │  ")
        sys.stdout.flush()
        line_input = input()
        if line_input.strip().upper() == "END":
            break
        lines.append(line_input)

    raw_task = "\n".join(lines).strip()
    if not raw_task:
        print_error("No task provided.")
        return

    print_info("Forge is planning...")

    response = ai.chat(Planner.generate(raw_task))

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        task_data = json.loads(response[start:end])
        task_data["created_at"] = datetime.now().isoformat()
        task_data["status"] = "planned"
        save_task_file(task_data)
        print_plan(task_data)

    except Exception as e:
        print_error(f"Could not parse plan: {e}")
        print_info("Raw response saved to tasks/execution/raw_plan.txt")
        os.makedirs(EXECUTION_DIR, exist_ok=True)
        with open(f"{EXECUTION_DIR}/raw_plan.txt", "w") as f:
            f.write(response)


def cmd_start(ai: AI, active_executor: dict = None):
    from tasks.execution.executor import Executor

    data = load_task_file()

    if not data:
        print_agent(Chat.NO_TASK_TO_START)
        return

    if data.get("status") == "running":
        print_agent(Chat.TASK_ALREADY_RUNNING)
        return

    if data.get("status") not in ("planned", "paused"):
        print_error(f"Task status is '{data.get('status')}' — cannot start.")
        return

    data["status"] = "running"
    data["started_at"] = datetime.now().isoformat()
    save_task_file(data)

    print_success(f"Starting: {data.get('title')}")
    print()

    def on_update(event: str, payload):
        if event == "subtask_start":
            st = payload
            print_section(f"SUBTASK {st['id']} / {len(data['subtasks'])}")
            print(f"  {st['description']}")
            print()

        elif event == "subtask_done":
            st = payload["subtask"]
            print_success(f"[{st['id']}] done in {payload['steps']} steps")
            print(f"  {payload['result'][:120]}")
            print()

        elif event == "subtask_failed":
            print_error(f"Subtask {payload['subtask']['id']} failed")
            print()
            print_agent(payload["reason"])

        elif event == "task_done":
            line("═")
            print_success("All subtasks completed.")
            line("═")

        elif event == "task_failed":
            line("─")
            print_error("Task stopped — requires your input to continue.")
            print()
            if payload.get("reason"):
                print_agent(payload["reason"])

        elif event == "task_stopped":
            line("─")
            print_info(payload.get("message", "Execution paused."))
            line("─")

    try:
        executor = Executor(ai)
        if active_executor is not None:
            active_executor["ref"] = executor
        executor.run(on_update=on_update)
    except FileNotFoundError as e:
        print_error(str(e))
    except Exception as e:
        print_error(f"Execution engine crashed: {type(e).__name__}: {e}")
        logger.crash("cmd_start", e)
        if os.getenv("DEV_MODE", "false").lower() == "true":
            import traceback as tb
            print()
            print("  ── traceback ──────────────────────────────────────")
            for ln in tb.format_exc().splitlines():
                print(f"  {ln}")
            print("  ───────────────────────────────────────────────────")
            print()
    finally:
        if active_executor is not None:
            active_executor["ref"] = None


def cmd_status():
    print_section("EXECUTION STATUS")
    data = load_task_file()

    if not data:
        print_info("No active task found.")
        return

    status = data.get("status", "unknown")
    status_labels = {
        "planned":  "○  Planned — type /start to execute",
        "running":  "▶  Running",
        "done":     "✓  Completed",
        "paused":   "‖  Paused",
        "error":    "✗  Error",
    }

    print(f"  Task    : {data.get('title', 'Untitled')}")
    print(f"  Status  : {status_labels.get(status, status)}")
    print()

    icons = {"done": "✓", "in_progress": "▶", "pending": "○", "error": "✗"}
    for st in data.get("subtasks", []):
        icon = icons.get(st["status"], "?")
        result_preview = ""
        if st.get("result"):
            result_preview = f"\n         └─ {str(st['result'])[:56]}..."
        print(f"  {icon}  [{st['id']:>2}]  {st['description']}{result_preview}")
    print()


def cmd_reset(ai: AI):
    ai.reset()
    print_success("History cleared. System prompt preserved.")


def cmd_exit():
    """Limpia el estado de sesion al salir."""
    import shutil

    session_dirs = [
        Path("context/task"),
        Path("context/project"),
        Path("tasks/execution"),
    ]
    session_files = [
        Path("tasks/project/task.json"),
    ]

    for d in session_dirs:
        if d.exists():
            shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)

    for f in session_files:
        if f.exists():
            f.unlink()

    logger.info("Session ended — context and task state cleared.")


# ─────────────────────────────────────────────
#  CONCURRENT INPUT LISTENER
# ─────────────────────────────────────────────

class InputListener:
    def __init__(self):
        self.command_queue: list[str] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _listen(self):
        print_info("Forge is thinking. Type /status anytime.")
        while self._running:
            try:
                sys.stdout.write("  » ")
                sys.stdout.flush()
                cmd = input().strip()
                if cmd:
                    with self._lock:
                        self.command_queue.append(cmd)
            except EOFError:
                break

    def flush(self, ai: AI):
        with self._lock:
            cmds = self.command_queue[:]
            self.command_queue.clear()

        for cmd in cmds:
            if cmd == "/status":
                cmd_status()
            elif cmd == "/reset":
                cmd_reset(ai)
            elif cmd == "/help":
                print_help()
            else:
                print_info(f"'{cmd}' queued while Forge was busy — type it again.")


# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────

def main():
    header()
    print_info("Type /help to see available commands.")
    print_info("Type your message or a /command below.")
    print()

    ai = AI(system_prompt=SYSTEM)
    listener = InputListener()
    active_executor = {"ref": None}  # referencia mutable al executor activo

    while True:
        try:
            print_user_prompt()
            user_input = input().strip()
            print("└" + "─" * (WIDTH - 1))

            if not user_input:
                continue

            if user_input == "/exit":
                cmd_exit()
                line("═")
                print("  Goodbye.")
                line("═")
                break

            elif user_input == "/reset":
                cmd_reset(ai)

            elif user_input == "/help":
                print_help()

            elif user_input == "/task":
                cmd_task(ai)

            elif user_input == "/start":
                cmd_start(ai, active_executor)

            elif user_input == "/status":
                cmd_status()

            elif user_input == "/stop":
                if active_executor["ref"]:
                    active_executor["ref"].request_stop()
                    print_info("Stop requested — Forge will pause after the current subtask.")
                else:
                    print_info("No task is currently running.")

            else:
                print_info("Forge is thinking...")
                response = ai.chat(user_input)
                print_agent(response)

        except KeyboardInterrupt:
            listener.stop()
            with listener._lock:
                listener.command_queue.clear()
            print()
            line("─")
            print_info("Use /exit to quit cleanly.")
            print()
        except Exception as e:
            print_error(f"Unexpected error: {type(e).__name__}: {e}")
            logger.crash("main_loop", e)
            if os.getenv("DEV_MODE", "false").lower() == "true":
                import traceback
                print()
                for ln in traceback.format_exc().splitlines():
                    print(f"  {ln}")
                print()


if __name__ == "__main__":
    main()