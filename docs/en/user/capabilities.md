# Capabilities

What Forge can and cannot do.

---

## What Forge Can Do

### File Operations

Forge can read, write, and modify files within your project directory.

- Read any file in full or by line range
- Create new files and directories
- Write and overwrite files
- Patch specific sections of a file without rewriting the whole file
- Search for files by name pattern (`*.py`, `test_*.py`, `**/*.json`)
- Search for text inside files (like `grep`)
- Show directory structure

**Example tasks:**
- "Create a `config.py` file with these settings..."
- "Read `src/auth.py` and refactor the login function to use JWT"
- "Find all Python files that import `os.path` and list them"

---

### Code Execution

Forge can run Python code within your project.

- Execute existing Python files
- Run Python code snippets in a sandboxed environment
- Run pytest test suites with full output
- Install Python packages with pip

All code execution happens inside a sandbox — a temporary directory isolated from the rest of your system.

**Example tasks:**
- "Run `src/main.py` and show me the output"
- "Write tests for `math_utils.py` and run them"
- "Install `requests` and `pytest`"

---

### Terminal Commands

Forge can run a controlled set of shell commands.

**Git operations:** `status`, `log`, `diff`, `add`, `commit`, `branch`, `checkout`, `stash`, `push`, `pull`, `fetch`, `init`, `clone`, `merge`, `rebase`, `tag`, `blame`, `rev-parse`

**HTTP requests:** `curl` and `wget` with any flags

**Custom commands:** Additional commands can be whitelisted via `FORGE_EXTRA_COMMANDS` in `.env`

**Example tasks:**
- "Check git status and show me the last 5 commits"
- "Add all changed files and commit with message `fix: update auth logic`"
- "Fetch the response from `https://api.example.com/users`"

---

### Documentation Search

Forge can search and read technical documentation.

| Source | What it covers |
|--------|---------------|
| `python` | Python 3 official docs |
| `mdn` | JavaScript, HTML, CSS, Web APIs |
| `nodejs` | Node.js official docs |
| `rust` | Rust standard library |
| `pypi` | Python package index |
| `github` | GitHub repository search |

Forge can also fetch any URL and read it as clean text, and read raw files directly from GitHub repositories.

**Example tasks:**
- "Search the Python docs for `asyncio.gather` and explain how to use it"
- "Read the README from `github.com/psf/requests` and summarize the installation"

---

### System Information

Forge can inspect the development environment.

- Installed runtime versions (Python, Node, Go, Rust, Java)
- Available dev tools (git, docker, pytest, ruff, black)
- Disk usage
- Which ports are currently in use
- Environment variables (non-sensitive ones only)

**Example tasks:**
- "Check if pytest is installed and what version"
- "Is port 8000 in use?"
- "How much disk space is free in the project directory?"

---

## What Forge Cannot Do

### Outside the Project Directory

Forge is strictly confined to `FORGE_PROJECT_ROOT`. It cannot:

- Read, write, or delete files outside the project
- Access system directories (`/etc`, `/usr`, `/root`, etc.)
- Read or modify `.env`, `.ssh`, or other sensitive files

This is enforced at the security layer and cannot be overridden from a task description.

### Destructive Operations Without Confirmation

Forge requires explicit `confirmed=true` to delete files or directories. The agent cannot self-authorize deletions — you must explicitly approve them when the agent asks.

### Shell Scripts

Running `.sh`, `.bash`, or `.zsh` files directly is blocked. Use `tools/terminal` for shell commands or `tools/code` for Python scripts.

### Arbitrary Shell Commands

Only whitelisted commands can run in the terminal. Commands like `rm`, `sudo`, `chmod`, `systemctl`, and others are permanently blocked regardless of task description.

### Accessing Your Secrets

API keys, passwords, tokens, and other sensitive environment variables are permanently blocked from agent access. The agent can never read `GROQ_API_KEY`, `DATABASE_URL`, or any variable matching known secret patterns.

### Parallel Execution

Forge executes subtasks sequentially. It cannot run multiple subtasks at the same time.

---

## Limitations to Know

**Context window:** Forge uses an LLM with a 128k token context. For very long sessions, the context manager automatically compresses older history into a summary. This is transparent but may occasionally cause the agent to lose fine details from early in the session.

**Planner accuracy:** The quality of the execution plan depends on how clearly you describe the task. Vague descriptions lead to vague plans. If the plan doesn't look right, type `/task` again with a more detailed description.

**Model dependency:** Forge's reasoning quality depends on the LLM model configured in `GROQ_MODEL`. The recommended model is `llama-3.3-70b-versatile`. Smaller models (like `llama-3.1-8b-instant`) may produce incorrect JSON or make poor tool choices.