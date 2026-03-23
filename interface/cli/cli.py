import threading
import sys
import os
import json
from datetime import datetime
from llm.ai import AI

# ─────────────────────────────────────────────
#  DISPLAY HELPERS
# ─────────────────────────────────────────────

WIDTH = 64

def line(char="─", width=WIDTH):
    print(char * width)

def header():
    os.system("clear")
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
    print("  /reset    Clear conversation history")
    print("  /task     Load a new task into tasks/")
    print("  /status   Show current subtask execution status")
    print("  /help     Show this menu")
    print("  /exit     Exit Forge")
    print("─" * WIDTH)
    print("  While agent is running you can type:")
    print("  /status   Check progress")
    print("  /stop     Interrupt current task  (coming soon)")
    print("═" * WIDTH)
    print()

# ─────────────────────────────────────────────
#  TASK HELPERS
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

def cmd_task(ai: AI):
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

    print_info("Sending to Forge planner...")

    planning_prompt = f"""You are a senior software engineer acting as a task planner.
Break down the following task into small, chronological subtasks.
Each subtask must be concrete and executable by an AI agent.

Respond ONLY with a valid JSON object in this exact format, no extra text:
{{
  "title": "short title of the overall task",
  "description": "original task description",
  "subtasks": [
    {{"id": 1, "description": "...", "status": "pending", "depends_on": [], "result": null, "context_written": []}},
    {{"id": 2, "description": "...", "status": "pending", "depends_on": [1], "result": null, "context_written": []}}
  ]
}}

Task:
{raw_task}"""

    response = ai.chat(planning_prompt)

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        task_data = json.loads(response[start:end])
        task_data["created_at"] = datetime.now().isoformat()
        task_data["status"] = "pending"
        save_task_file(task_data)

        print_success(f"Task planned: {task_data['title']}")
        print_section("SUBTASKS")
        for st in task_data["subtasks"]:
            deps = f"  (after {st['depends_on']})" if st["depends_on"] else ""
            print(f"  {st['id']:>2}.  {st['description']}{deps}")
        print()

    except Exception as e:
        print_error(f"Could not parse plan: {e}")
        print_info("Raw response saved for inspection.")
        os.makedirs(EXECUTION_DIR, exist_ok=True)
        with open(f"{EXECUTION_DIR}/raw_plan.txt", "w") as f:
            f.write(response)

def cmd_status():
    print_section("EXECUTION STATUS")
    data = load_task_file()
    if not data:
        print_info("No active task found in tasks/project/task.json")
        return

    print(f"  Task   : {data.get('title', 'Untitled')}")
    print(f"  Status : {data.get('status', 'unknown')}")
    print()

    subtasks = data.get("subtasks", [])
    if not subtasks:
        print_info("No subtasks defined.")
        return

    icons = {"done": "✓", "in_progress": "▶", "pending": "○", "error": "✗"}
    for st in subtasks:
        icon = icons.get(st["status"], "?")
        print(f"  {icon}  [{st['id']:>2}]  {st['description']}")
        if st.get("result"):
            print(f"         └─ {st['result'][:60]}...")
    print()

def cmd_reset(ai: AI):
    ai.reset()
    print_success("History cleared. System prompt preserved.")

# ─────────────────────────────────────────────
#  CONCURRENT INPUT LISTENER
#  Runs in a separate thread while agent works
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
        print_info("Agent is working. You can type /status or /stop anytime.")
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
        """Process any commands typed while agent was running."""
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
                print_info(f"Command '{cmd}' queued but agent was busy. Type it again.")

# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are Forge, an expert AI agent built to assist software developers.
You are precise, concise, and technical. You reason step by step.
When planning tasks, you always break them into small, executable subtasks.
You prefer clarity over verbosity."""

def main():
    header()
    print_info("Type /help to see available commands.")
    print_info("Type your message or a command below.")
    print()

    ai = AI(system_prompt=SYSTEM_PROMPT)
    listener = InputListener()

    while True:
        try:
            print_user_prompt()
            user_input = input().strip()
            print("└" + "─" * (WIDTH - 1))

            if not user_input:
                continue

            # ── Commands ──
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

            elif user_input == "/status":
                cmd_status()

            # ── Chat ──
            else:
                listener.start()
                response = ai.chat(user_input)
                listener.stop()
                listener.flush(ai)
                print_agent(response)

        except KeyboardInterrupt:
            print()
            line("─")
            print_info("Use /exit to quit cleanly.")
            print()

if __name__ == "__main__":
    main()