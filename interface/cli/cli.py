import threading
import sys
import os
import json
from datetime import datetime
from llm.ai import AI
from llm.prompts import SYSTEM, Planner, Chat

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
    print("  /status   Show subtask execution progress")
    print("  /reset    Clear conversation history")
    print("  /help     Show this menu")
    print("  /exit     Exit Forge")
    print("─" * WIDTH)
    print("  While agent is running:")
    print("  /status   Check progress at any time")
    print("  /stop     Interrupt execution  (coming soon)")
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
    with open(TASK_FILE, "r") as f:
        return json.load(f)


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
    if task_status() == "running":
        print_agent(Chat.TASK_ALREADY_RUNNING)
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


def cmd_start(ai: AI):
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
    print_info("Type /status to check progress.")
    print()

    # Execution engine connects here — tasks/execution/ coming next
    print_agent(
        f"Plan locked. {len(data.get('subtasks', []))} subtasks queued.\n"
        f"Next: {data['subtasks'][0]['description']}\n\n"
        f"[ execution engine not yet connected ]"
    )


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

    while True:
        try:
            print_user_prompt()
            user_input = input().strip()
            print("└" + "─" * (WIDTH - 1))

            if not user_input:
                continue

            if user_input == "/exit":
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
                cmd_start(ai)

            elif user_input == "/status":
                cmd_status()

            else:
                listener.start()
                response = ai.chat(user_input)
                listener.stop()
                listener.flush(ai)
                print_agent(response)

        except KeyboardInterrupt:
            listener.stop()
            with listener._lock:
                listener.command_queue.clear()
            print()
            line("─")
            print_info("Use /exit to quit cleanly.")
            print()


if __name__ == "__main__":
    main()