# Getting Started with Forge

Forge is a terminal-based AI agent for developers. This guide walks you through installation, configuration, and your first task.

---

## Requirements

- **OS**: Linux (tested on Arch Linux, Ubuntu 24)
- **Python**: 3.11 or higher
- **Groq API key**: Free at [console.groq.com](https://console.groq.com)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/youruser/forge.git
cd forge
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install groq python-dotenv tiktoken requests beautifulsoup4 html2text
```

### 4. Configure your environment

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

The minimum required configuration:

```env
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
FORGE_PROJECT_ROOT=/absolute/path/to/your/project
```

> **Important:** `FORGE_PROJECT_ROOT` must be the absolute path to the directory you want Forge to work in. Forge cannot access files outside this directory.

### 5. Run Forge

```bash
python app.py
```

---

## Your First Task

When Forge starts you will see the main prompt:

```
┌─ You ──────────────────────────────────────────────────
│  >
```

Type `/task` and press Enter. Forge will ask you to describe what you want:

```
/task
```

```
Describe the task in detail.
Type END on a new line when done.

│  Create a Python script called hello.py that prints "Hello from Forge"
│  and run it.
│  END
```

Forge will generate a plan and show it to you:

```
PLAN  ·  Hello Script
─────────────────────────────────────────────
  Risk      ○  LOW
  Subtasks  1
─────────────────────────────────────────────
   1.  Create hello.py with print statement and run it
─────────────────────────────────────────────
  Plan is ready. Review the subtasks above.
  /start — execute the plan as shown
```

Review the plan. If it looks correct, type `/start` to execute it.

> Forge will never execute anything without your explicit `/start` command.

---

## Tips for Writing Good Tasks

**Be specific.** Instead of "set up tests", say "create pytest tests for the `auth.py` module covering login, logout, and token validation, and run them."

**Mention file paths.** "Create `src/utils/logger.py`" is better than "create a logger file."

**One objective per task.** Forge works best when the goal is clear. Complex multi-objective tasks can be split across multiple `/task` invocations.

**Describe the expected outcome.** "Run the tests and report how many passed" helps the agent know when it's done.

---

## Next Steps

- [Commands Reference](commands.md) — All available commands and what they do
- [Capabilities](capabilities.md) — What Forge can and cannot do
- [Risks and Safety](risks.md) — Understanding the security model