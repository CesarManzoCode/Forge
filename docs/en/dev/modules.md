# Modules Reference

Detailed documentation for every module in Forge.

---

## `app.py`

**Entry point.** Handles bootstrap and argument parsing.

**Responsibilities:**
- Adds the project root to `sys.path` so all imports resolve correctly regardless of where the script is invoked from
- Loads `.env` before any module that reads environment variables at import time
- Parses CLI arguments (`--dev` flag)
- Calls `interface/cli/cli.py:main()`

**Arguments:**
- `--dev` — Forces `DEV_MODE=true`, overriding the `.env` value

**Usage:**
```bash
python app.py           # Normal mode
python app.py --dev     # Developer mode
```

**Key detail:** `load_dotenv()` is called here, before imports of `llm/`, `tasks/`, or `src/`. This is intentional — `dev.py` reads `DEV_MODE` at module level, so the env must be loaded before any of those modules are imported.

---

## `llm/ai.py`

**Groq API client with context window management.**

### Class: `AI`

```python
AI(system_prompt: str = None)
```

**Constructor:** Initializes the Groq client from `GROQ_API_KEY`, sets the model from `GROQ_MODEL`, and adds the system prompt as the first history entry.

**Methods:**

```python
chat(message: str) -> str
```
Adds `message` to history, calls `_maybe_compress()`, sends the full history to Groq, appends the response, returns raw response string.

```python
reset()
```
Clears history but preserves the system prompt. Used between subtasks to discard execution observations while keeping the agent's role definition.

```python
inject_context(content: str, label: str = "context")
```
Adds a user/assistant pair to history without going through the chat flow. The user message contains the labeled content; the assistant responds with "Understood." Used to inject tool lists, project context, and user preferences.

```python
token_count() -> int
```
Returns current token count using tiktoken's `cl100k_base` encoding. Falls back to character-based estimation (`chars // 4`) if tiktoken is unavailable.

```python
context_usage() -> dict
```
Returns `{tokens, limit, threshold, percent, will_compress_at}`.

**Context compression (`_maybe_compress`):**

Triggered before each API call if token count exceeds `FORGE_COMPRESS_AT * FORGE_CONTEXT_LIMIT` (default: 80% of 128k = 102,400 tokens).

Compression strategy:
1. Keeps system prompt intact
2. Keeps last 4 user/assistant pairs (the most recent context)
3. Takes all messages in the middle and sends them to a separate summarization call
4. Replaces middle messages with a `[HISTORY SUMMARY]` entry

The summarization call uses `max_tokens=300` to produce a concise technical summary.

**Environment variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | (required) | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Model to use |
| `FORGE_CONTEXT_LIMIT` | `128000` | Max tokens for the model |
| `FORGE_COMPRESS_AT` | `0.80` | Compression trigger threshold |

---

## `llm/prompts.py`

**Centralized prompt library.** All LLM prompts in one place.

**Module-level constant:**
```python
LANGUAGE = os.getenv("FORGE_LANGUAGE", "English")
```
Read once at import time. Used in all user-facing prompts.

### `SYSTEM`

The main Forge persona prompt. Defines traits, capabilities, and language. Used as system prompt for the chat AI in `cli.py`.

### `class Planner`

```python
Planner.generate(task_description: str) -> str
```
Full planner prompt. Includes rules for subtask granularity, the BAD/GOOD examples, and the exact JSON format required. Returns the string to pass to `ai.chat()`.

```python
Planner.clarify(task_description: str, question: str) -> str
```
Used when the planner needs to ask a clarifying question before generating a plan.

```python
Planner.replan(original_plan: str, feedback: str) -> str
```
Used to revise an existing plan based on user feedback.

### `class Executor`

```python
Executor.run_subtask(subtask: dict, project_context: str, task_context: str) -> str
```
The prompt sent to start each subtask in the ReAct loop. Includes project context, previous subtask results, and the current subtask description. Instructs the agent to respond with JSON only.

### `class Chat`

String constants for system messages shown to the user. Not sent to the LLM.

---

## `llm/dev.py`

**Developer mode output.** Zero overhead when disabled.

**Module-level constant:**
```python
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
```

**Functions:**

```python
dev_log_request(model: str, messages: list[dict]) -> float
```
Prints the `[DEV:REQUEST]` block. Truncates long messages to 300 chars. Returns `time.time()` for timing, even when dev mode is off (no-op path still returns timestamp for the caller).

```python
dev_log_response(raw_response: str, start_time: float)
```
Prints the `[DEV:RESPONSE]` block. Detects JSON in the response and pretty-prints it. Shows elapsed time and response length.

---

## `interface/cli/cli.py`

**Full terminal interface.** ~450 lines. Single file for the entire CLI.

### Display helpers

All display functions write directly to stdout. They are stateless — no side effects beyond printing.

| Function | Purpose |
|----------|---------|
| `header()` | Clears terminal, prints ASCII logo |
| `print_agent(text)` | Wraps text in `┌─ Forge ─` box |
| `print_user_prompt()` | Prints `┌─ You ─` and cursor |
| `print_plan(data)` | Formats and prints a task plan |
| `print_help()` | Prints command reference |
| `print_info/success/error(msg)` | Status messages |

`WIDTH = 64` controls all formatting. Change this constant to adjust the display width.

### Command functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `cmd_task` | `(ai, active_executor)` | Opens task editor, calls planner, saves plan |
| `cmd_start` | `(ai, active_executor)` | Creates Executor, runs it, handles events |
| `cmd_stop` | — | Sets stop flag on active executor |
| `cmd_status` | `(ai=None)` | Shows task state and context usage |
| `cmd_reset` | `(ai)` | Clears AI history, optionally clears task |
| `cmd_exit` | `()` | Cleans session state, called before exit |

### `InputListener`

A threading helper that listens for commands while the agent is working. Uses a daemon thread with a `threading.Lock`-protected queue. Currently unused in the main chat flow (removed to prevent `input()` conflicts) but retained for the execution engine's future async use.

### Main loop

```python
def main():
    ai = AI(system_prompt=SYSTEM)
    active_executor = {"ref": None}

    while True:
        user_input = input()
        # dispatch to command functions or ai.chat()
```

`active_executor` is a mutable dict (not a plain variable) so that `cmd_start` can update it and the main loop can check it for `/stop`.

---

## `src/security/config.py`

**Security rules.** Fixed lists and configurable values.

### Fixed rules (hardcoded, never overridable)

- `BLOCKED_ABSOLUTE` — system directory prefixes
- `BLOCKED_FILENAMES` — sensitive filenames
- `BLOCKED_EXEC_EXTENSIONS` — extensions that cannot be executed

### Configurable rules (via `.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `FORGE_PROJECT_ROOT` | `os.getcwd()` | Root of the allowed file tree |
| `FORGE_ALLOWED_EXTENSIONS` | `.py,.js,.ts,.go,.rs,.rb,.java` | Executable extensions |
| `FORGE_MAX_WRITE_BYTES` | `1048576` (1MB) | Max bytes per write operation |
| `FORGE_SANDBOX` | `true` | Enable/disable execution sandbox |
| `FORGE_EXEC_TIMEOUT` | `30` | Code execution timeout in seconds |

---

## `src/security/guards.py`

**Validation functions.** Called by every tool before any file or execution operation.

```python
guard_path(path: str, operation: str = "access") -> Path
```
Resolves relative paths against `project_root`. Checks containment, blocked directories, and blocked filenames. Returns resolved `Path` on success, raises `SecurityError` on failure.

```python
guard_write(path: str, content: str | bytes) -> Path
```
Calls `guard_path` then checks content size against `max_write_bytes`.

```python
guard_exec(code: str, language: str) -> str
```
Validates language against allowed extensions. Runs code in a temp directory with the configured timeout. Returns stdout.

```python
@require_safe_path(arg_index=0, operation="read")
@require_safe_write(path_index=0, content_index=1)
```
Decorators for applying guards to tool functions. The decorated function only runs if the guard passes.

**`SecurityError`** is a custom exception class. Callers (especially `react.py`) catch it specifically to distinguish security blocks from other errors.

---

## `src/tools/file/__init__.py`

**File system operations.**

| Function | Signature | Notes |
|----------|-----------|-------|
| `read_file` | `(path)` | Full file content as string |
| `read_lines` | `(path, start, end)` | 1-indexed inclusive range, returns with line numbers |
| `write_file` | `(path, content, overwrite=True)` | Creates parent dirs, raises if exists and overwrite=False |
| `append_file` | `(path, content)` | Creates if not exists |
| `patch_file` | `(path, old, new)` | Fails if `old` appears 0 or 2+ times |
| `create_dir` | `(path)` | `mkdir -p` equivalent |
| `delete_file` | `(path, confirmed=False)` | Requires `confirmed=True` |
| `delete_dir` | `(path, confirmed=False)` | Recursive, blocks project root deletion |
| `move` | `(src, dst)` | Works for files and directories |
| `find_files` | `(pattern, directory=".", max_results=50)` | Glob pattern |
| `grep` | `(pattern, directory=".", extensions=None, max_results=30)` | Returns list of `{file, line_number, line_content}` |
| `tree` | `(directory=".", max_depth=3)` | Ignores `.git`, `__pycache__`, `node_modules` |

---

## `src/tools/code/__init__.py`

**Code execution.**

| Function | Signature | Notes |
|----------|-----------|-------|
| `run_file` | `(path, args=None)` | Runs `.py` file with project Python |
| `run_code` | `(code)` | Runs snippet in temp sandbox |
| `run_tests` | `(path="tests", flags=None)` | Sets PYTHONPATH to handle subdirectory imports |
| `install_deps` | `(packages=None, requirements_file=None)` | Falls back to `requirements.txt` if no args |
| `check_env` | `()` | Returns `{python, pip, pytest}` versions |

**PYTHONPATH handling in `run_tests`:**
The function constructs `PYTHONPATH` as `project_root:test_dir:test_dir_parent` before running pytest. This allows tests in subdirectories to import modules from parent directories without manual `conftest.py` configuration.

---

## `src/tools/terminal/__init__.py`

**Controlled shell execution.**

The whitelist has two levels:
1. Binary level — `BASE_WHITELIST` dict with allowed commands
2. Subcommand level — for `git`, specific subcommands are listed; for `curl/wget`, any flags are allowed

```python
HARD_BLOCKED = {"rm", "sudo", "bash", "python", ...}
```
These can never be added to the whitelist via `FORGE_EXTRA_COMMANDS`.

```python
run_command(command: str, cwd: str = None) -> str
```
Parses command with `shlex.split()`, validates against whitelist, runs with merged stdout/stderr, truncates output at `FORGE_TERMINAL_MAX_LINES`.

```python
git(subcommand: str, *args: str, cwd: str = None) -> str
curl(url: str, *flags: str) -> str
whitelist_info() -> dict
```

**Environment variable:**
`FORGE_EXTRA_COMMANDS` — comma-separated list of additional allowed commands.

---

## `src/tools/internet/__init__.py`

**Documentation and web access.**

```python
search_docs(query: str, source: str = "python") -> str
```
Constructs search URL for the given source, fetches page, strips nav/header/footer with BeautifulSoup, converts to Markdown with html2text. Returns Markdown string prefixed with source URL.

```python
fetch_url(url: str) -> str
```
Fetches any URL, converts to Markdown. Only accepts `http`/`https`.

```python
fetch_github_raw(owner, repo, path, branch="main") -> str
```
Constructs `raw.githubusercontent.com` URL. If 404 with `main`, suggests trying `master`.

**Dependencies:** `requests`, `beautifulsoup4`, `html2text`

**Environment variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| `FORGE_HTTP_TIMEOUT` | `15` | Seconds per HTTP request |
| `FORGE_MAX_CONTENT_CHARS` | `12000` | Max chars returned to LLM |

---

## `src/tools/system/__init__.py`

**Development environment inspection.**

```python
env_info() -> dict
```
Returns `{os, shell, project_root, venv_active, venv_name, runtimes, dev_tools}`. Detects Python, Node, Go, Rust, Java, git, docker, pytest, ruff, black.

```python
running_ports(ports: list[int] = None) -> dict[int, bool]
```
Checks TCP connectivity on each port. Default ports: `3000, 4000, 5000, 5173, 8000, 8080, 8888, 9000`.

```python
disk_usage(path: str = None) -> dict
```
Returns `{path, total_mb, used_mb, free_mb, used_percent}`.

```python
get_env_var(key: str) -> str
install_env_vars(prefix: str = "FORGE_") -> dict
```
`get_env_var` blocks any key matching `_SENSITIVE_KEYS` patterns. `list_env_vars` only shows variables with the given prefix and masks any that look sensitive.

---

## `tasks/execution/registry.py`

**Tool registry.** Maps string names to Python functions for the agent.

```python
TOOLS: dict[str, dict]
```
Each entry has `fn`, `description`, and `args` (schema with `?` suffix for optional).

```python
class ToolRegistry:
    def call(self, tool_name: str, args: dict) -> str
    def tool_list(self) -> str
```

`call()` validates required args, handles special cases for `git()` (uses `*args`) and `curl()`, then normalizes the return value to string. Lists and dicts are JSON-serialized.

`tool_list()` returns a formatted string of all tools for injection into the LLM prompt.

```python
registry = ToolRegistry()  # global instance
```

---

## `tasks/execution/react.py`

**ReAct loop implementation.**

### `Step` dataclass
```python
@dataclass
class Step:
    thought: str
    tool: str | None
    args: dict
    observation: str | None
    error: str | None
```

### `ReactResult` dataclass
```python
@dataclass
class ReactResult:
    success: bool
    result: str
    steps: list[Step]
    steps_taken: int
```

### `ReactLoop`

```python
ReactLoop(ai: AI)
run(subtask, project_context, task_context) -> ReactResult
```

The loop runs up to `FORGE_MAX_STEPS` (default 20) iterations. Each iteration:
1. Parses LLM JSON response
2. If `done: true` → returns `ReactResult(success=True)`
3. If tool proposed → executes via `registry.call()`
4. If error → returns `ReactResult(success=False)`
5. Sends observation back to LLM

If JSON is invalid, one retry is attempted with an explicit correction request before aborting.

**Observation prompt optimization:** The first observation includes the JSON format reminder. Subsequent observations are just `[tool_name] result` — no repetition.

---

## `tasks/execution/executor.py`

**Subtask orchestrator.**

### `Executor`

```python
Executor(ai: AI)
run(on_update=None)
request_stop()
```

`run()` creates a fresh `exec_ai = AI(system_prompt=_EXECUTION_SYSTEM)` for execution. This is separate from the CLI's chat AI to prevent history contamination.

**`on_update` callback events:**
| Event | Data |
|-------|------|
| `subtask_start` | subtask dict |
| `subtask_done` | `{subtask, result, steps}` |
| `task_done` | task dict |
| `task_failed` | `{subtask, reason}` |
| `task_stopped` | `{message}` |

**Tool filtering (`_filter_tools`):**
Analyzes subtask description for category keywords. Always includes `file` tools. Adds other categories (`code`, `terminal`, `internet`, `system`) if matching keywords are found in Spanish or English.

**Context flow per subtask:**
1. `exec_ai.reset()` between subtasks
2. Re-inject updated `context/task/` content
3. Inject filtered tool list for the next subtask

---

## `logs/logger.py`

**Three-channel logging with rotation.**

```python
logger = Logger()  # global instance

logger.error(message, exc=None)
logger.crash(context, exc)
logger.task_done(task)
logger.task_failed(task, reason)
logger.agent_action(tool, args, result, subtask_id=None)
logger.agent_error(tool, args, error, subtask_id=None)
logger.info(message)
```

**Log files:**
- `logs/errors.log` — errors and crashes with tracebacks
- `logs/tasks.log` — task completion summaries and info messages
- `logs/actions.log` — tool calls with args and results

**Rotation:** When a log file exceeds `FORGE_LOG_MAX_MB` (default 5MB), it is renamed to `.log.1` and a new empty file is created. Only one backup is kept per file type.