# Forge

**AI Agent for Developers** — An autonomous coding assistant that plans, executes, and delivers development tasks using a ReAct reasoning loop.

```
  ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
  ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
  █████╗  ██║   ██║██████╔╝██║  ███╗█████╗
  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝
  ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
  ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
```

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-lightgrey)](https://linux.org)

---

## What is Forge?

Forge is a terminal-based AI agent designed exclusively for software developers. Unlike general-purpose AI assistants, Forge can autonomously execute complex development tasks by breaking them into chronological subtasks and using a set of controlled tools to complete them.

You describe what you want. Forge plans it, shows you the plan, and executes it only after your confirmation.

## Key Features

- **ReAct reasoning loop** — Think, Act, Observe. The agent reasons step by step before using any tool.
- **Controlled execution** — Nothing runs until you type `/start`. You review the plan first.
- **Developer-focused tools** — File operations, code execution, pytest, git, documentation search, GitHub raw access.
- **Security by design** — Path guards, command whitelist, execution sandbox. The agent cannot touch system files.
- **Context persistence** — Completed tasks inform future tasks within a session.
- **Developer mode** — Full API request/response visibility with `DEV_MODE=true`.

## Requirements

- Linux (tested on Arch Linux)
- Python 3.11+
- A [Groq API key](https://console.groq.com)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/youruser/forge.git
cd forge

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install groq python-dotenv tiktoken requests beautifulsoup4 html2text

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Run
python app.py
```

## Basic Usage

```
/task          Describe a task for Forge to plan
/start         Execute the current plan
/status        Show subtask progress and context usage
/stop          Pause execution after current subtask
/reset         Clear conversation history
/exit          Exit Forge (clears session context)
```

## Documentation

| Language | User Guide | Developer Guide |
|----------|-----------|-----------------|
| English  | [docs/en/user/](docs/en/user/) | [docs/en/dev/](docs/en/dev/) |
| Español  | [docs/es/user/](docs/es/user/) | [docs/es/dev/](docs/es/dev/) |

## Project Structure

```
Forge/
├── app.py                    Entry point
├── llm/                      LLM connection and prompts
├── interface/cli/            Terminal interface
├── src/
│   ├── security/             Path guards and sandbox
│   └── tools/                file, code, terminal, internet, system
├── tasks/execution/          ReAct loop and executor
├── context/                  Session context (cleared on exit)
├── memory/                   Persistent user preferences
├── logs/                     Error, task, and action logs
└── docs/                     Documentation
```

## Security Notice

Forge operates exclusively within the project directory defined by `FORGE_PROJECT_ROOT`. It cannot read, write, or execute files outside this boundary. Sensitive environment variables (API keys, secrets) are permanently blocked from agent access.

See [docs/en/user/risks.md](docs/en/user/risks.md) for a complete security overview.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE).