# Environment Variables Reference

Complete reference for all `.env` variables in Forge.

---

## Required

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key. Get one free at [console.groq.com](https://console.groq.com) |
| `FORGE_PROJECT_ROOT` | Absolute path to your project directory. Forge cannot access files outside this path. Example: `/home/user/myproject` |

---

## LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use. Recommended: `llama-3.3-70b-versatile`. Smaller models may produce inconsistent JSON. |
| `FORGE_LANGUAGE` | `English` | Language for agent responses. Example: `Spanish`, `French`, `German`. Affects all user-facing prompts and subtask descriptions. |
| `FORGE_CONTEXT_LIMIT` | `128000` | Maximum token context for the model. Set this to match your model's actual context window. |
| `FORGE_COMPRESS_AT` | `0.80` | Fraction of context limit at which history compression triggers. `0.80` = compress when 80% full (~102k tokens). Lower values compress more aggressively. |

---

## Security Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FORGE_SANDBOX` | `true` | Enable execution sandbox for `run_code()`. When `true`, code snippets run in an isolated temp directory. Set to `false` only for debugging. |
| `FORGE_EXEC_TIMEOUT` | `30` | Seconds before a code execution or shell command is killed. Applies to `run_code()`, `run_file()`, and `run_command()`. |
| `FORGE_ALLOWED_EXTENSIONS` | `.py,.js,.ts,.go,.rs,.rb,.java` | Comma-separated list of file extensions that can be executed via `run_code()`. Adding `.sh` here does not work — shell scripts are permanently blocked. |
| `FORGE_MAX_WRITE_BYTES` | `1048576` | Maximum bytes the agent can write in a single `write_file()` call. Default is 1MB. |

---

## Tool Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FORGE_MAX_STEPS` | `20` | Maximum ReAct steps per subtask before the agent is forced to stop. Increase for complex subtasks, decrease if the agent tends to loop. |
| `FORGE_EXTRA_COMMANDS` | *(empty)* | Comma-separated list of additional shell commands to whitelist. Example: `make,cargo,docker`. Note: permanently blocked commands (`rm`, `sudo`, etc.) cannot be added here. |
| `FORGE_TERMINAL_MAX_LINES` | `200` | Maximum lines of output returned from terminal commands. Output beyond this limit is truncated with a note. |
| `FORGE_HTTP_TIMEOUT` | `15` | Seconds before an HTTP request (via `internet/` tools) times out. |
| `FORGE_MAX_CONTENT_CHARS` | `12000` | Maximum characters returned from `fetch_url()` and `search_docs()`. Content beyond this is truncated. |

---

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `FORGE_LOG_MAX_MB` | `5` | Maximum size of each log file before rotation. When exceeded, the file is renamed to `.log.1` and a new file starts. |

---

## Developer Mode

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_MODE` | `false` | Enable developer output. Shows full API requests, raw LLM responses, and compression events. Can also be forced with `python app.py --dev`. |

---

## Example `.env`

```env
# ── Required ─────────────────────────────────────
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
FORGE_PROJECT_ROOT=/home/user/myproject

# ── LLM ──────────────────────────────────────────
GROQ_MODEL=llama-3.3-70b-versatile
FORGE_LANGUAGE=English
FORGE_CONTEXT_LIMIT=128000
FORGE_COMPRESS_AT=0.80

# ── Security ─────────────────────────────────────
FORGE_SANDBOX=true
FORGE_EXEC_TIMEOUT=30
FORGE_ALLOWED_EXTENSIONS=.py,.js,.ts,.go,.rs,.rb,.java
FORGE_MAX_WRITE_BYTES=1048576

# ── Tools ────────────────────────────────────────
FORGE_MAX_STEPS=20
FORGE_EXTRA_COMMANDS=
FORGE_TERMINAL_MAX_LINES=200
FORGE_HTTP_TIMEOUT=15
FORGE_MAX_CONTENT_CHARS=12000

# ── Logging ──────────────────────────────────────
FORGE_LOG_MAX_MB=5

# ── Developer ────────────────────────────────────
DEV_MODE=false
```

---

## Notes

**`FORGE_PROJECT_ROOT` is critical.** If this is set incorrectly, `guard_path()` will block all file operations because resolved paths won't match the expected root. Always use the absolute path.

**`FORGE_LANGUAGE` affects prompts, not tool output.** Tool results (file contents, git output, pytest results) are returned as-is. Only the agent's reasoning, summaries, and reports are in the configured language.

**`DEV_MODE=true` has no performance impact on production use.** The `dev_log_request` and `dev_log_response` functions are no-ops when `DEV_MODE=false`. The only overhead is the environment variable check at module import time.