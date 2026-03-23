# Commands Reference

Complete reference for all Forge CLI commands.

---

## Task Commands

### `/task`

Opens the task editor. Type your task description in as much detail as needed, then type `END` on a new line to submit.

Forge will:
1. Send the description to the planner
2. Generate a chronological list of subtasks
3. Show you the plan with risk level and subtask count
4. Wait for your confirmation before doing anything

```
/task
```

If a task already exists, Forge will ask if you want to overwrite it. A task in `running` status (active execution) cannot be overwritten — use `/stop` first.

**Writing effective task descriptions:**

```
Good: Create a FastAPI endpoint at POST /users that accepts name and email,
      validates both fields, and saves to a SQLite database. Include error
      handling for duplicate emails.

Bad:  Make a user endpoint.
```

---

### `/start`

Executes the current plan. Only works if a plan exists with status `planned` or `paused`.

```
/start
```

Once started, Forge runs each subtask in order. You can monitor progress with `/status`. Each subtask runs to completion before moving to the next.

---

### `/stop`

Requests a pause after the current subtask finishes. Forge will not interrupt a subtask mid-execution.

```
/stop
```

After stopping, the task status changes to `paused`. You can resume with `/start`.

> **Note:** `/stop` does not interrupt the current subtask. If you need to force-stop immediately, use `Ctrl+C`. The task will remain in `running` status and you will need to use `/reset` to clear it.

---

### `/status`

Shows the current task status, subtask progress, and context window usage.

```
/status
```

Output example:

```
── EXECUTION STATUS ─────────────────────────────
  Task    : Create auth module
  Status  : ▶  Running

  ✓  [ 1]  Create src/auth.py with JWT logic
         └─ File created with login, logout, token...
  ▶  [ 2]  Write tests for auth module
  ○  [ 3]  Run tests and report results

  Context : [████░░░░░░░░░░░░░░░░░░░░░░░░░░] 14.2%
              18,176 / 128,000 tokens
```

Subtask icons:
- `✓` Done
- `▶` In progress
- `○` Pending
- `✗` Error

---

## Session Commands

### `/reset`

Clears the AI conversation history. The system prompt is preserved. If a task is in an orphaned `running` or `error` state, Forge will also offer to clear the task file.

```
/reset
```

Use this when:
- The conversation has gone off track
- You want to start fresh without restarting Forge
- A task got stuck in `running` status after a crash

---

### `/help`

Shows a summary of all available commands.

```
/help
```

---

### `/exit`

Exits Forge cleanly. On exit, Forge automatically clears all session state:

- `context/task/` — subtask results from the current session
- `context/project/` — task summaries from the current session
- `tasks/project/task.json` — the current task file

> `memory/user.json` is **not** cleared on exit — your preferences persist across sessions.

```
/exit
```

---

## Developer Mode Commands

These are only visible when `DEV_MODE=true` in your `.env`.

When developer mode is active, Forge shows a detailed block before and after every API call:

```
┌─[DEV:REQUEST]──────────────────────────────────
│  model    : llama-3.3-70b-versatile
│  messages : 6
│  [0] SYSTEM (461 chars)  ...
│  [5] USER  ...
└────────────────────────────────────────────────

┌─[DEV:RESPONSE]─────────────────────────────────
│  time     : 0.63s
│  length   : 244 chars
│  ── json payload
│    { "thought": "...", "tool": "...", "args": {...} }
└────────────────────────────────────────────────
```

Additionally, if the context window manager compresses the history, a compression block is shown:

```
┌─[DEV:COMPRESSION]──────────────────────────────
│  before : 104,320 tokens
│  after  : 18,240 tokens
│  saved  : 86,080 tokens
└────────────────────────────────────────────────
```