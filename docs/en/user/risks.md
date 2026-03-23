# Risks and Safety

Understanding what Forge can and cannot do from a safety perspective.

---

## The Security Model

Forge operates on a principle of minimal trust. The agent is never trusted to self-authorize dangerous operations. Every sensitive operation goes through a validation layer before execution.

### Layers of Protection

```
Task description
      ↓
  LLM Planner (proposes tools and arguments)
      ↓
  Registry (validates tool exists and args are correct)
      ↓
  Security Guards (validates path, size, permissions)
      ↓
  Tool executes
```

The agent cannot bypass any of these layers from a task description.

---

## Path Security

Every file operation goes through `guard_path()` before execution. This function:

1. Resolves the path to its absolute form to prevent directory traversal attacks (`../../etc/passwd`)
2. Verifies the resolved path is inside `FORGE_PROJECT_ROOT`
3. Checks the path against a list of permanently blocked system directories
4. Checks the filename against a list of permanently blocked filenames

**Permanently blocked directories:**
`/etc`, `/usr`, `/bin`, `/sbin`, `/boot`, `/sys`, `/proc`, `/root`, `/var`

**Permanently blocked filenames:**
`.env`, `.ssh`, `.gnupg`, `id_rsa`, `id_ed25519`, `authorized_keys`, `passwd`, `shadow`, `sudoers`

There is no way to unblock these from the `.env` or from a task description. They are hardcoded.

---

## Command Security

Terminal commands go through a whitelist before execution. The whitelist has two layers:

1. **Binary whitelist** — only allowed executables can run (`git`, `curl`, `wget`, and any extras you add via `FORGE_EXTRA_COMMANDS`)
2. **Subcommand whitelist** — for `git`, only specific subcommands are allowed

**Permanently blocked commands** (cannot be added to the whitelist):
`rm`, `rmdir`, `dd`, `mkfs`, `sudo`, `su`, `chmod`, `chown`, `systemctl`, `passwd`, `useradd`, `nc`, `bash`, `sh`

These are blocked regardless of what the task description says.

---

## Execution Sandbox

When Forge runs code snippets via `run_code()`, it executes them in a temporary directory created specifically for that run. The sandbox:

- Has no access to your project files
- Is deleted after execution
- Has a configurable timeout (default: 30 seconds)

When running existing project files via `run_file()`, the file runs with the project root as the working directory. It has access to your project but not to system directories.

---

## Secrets Protection

The following environment variables are permanently blocked from agent access:

`GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN`, `NPM_TOKEN`, `PYPI_TOKEN`

Additionally, any variable whose name contains: `PASSWORD`, `PASSWD`, `TOKEN`, `API_KEY`, `PRIVATE_KEY`, `CERT`, `SSL`

The agent cannot read these values even if a task description explicitly asks for them.

---

## Destructive Operations

File and directory deletion requires `confirmed=True` to be passed explicitly. The agent cannot pass this flag on its own initiative — it must ask you first and you must approve.

Additionally, `delete_dir()` has an extra protection: it will never delete the project root directory even with `confirmed=True`.

---

## Risks to Be Aware Of

### The agent can modify your code

Forge can read and write files within your project. If you ask it to refactor a file, it will. If the result is not what you wanted, use `git diff` to review and `git checkout` to revert.

**Best practice:** Make sure you have a clean git state before running Forge on important files.

### The agent can run code

Forge can execute Python files and code snippets. A task like "run `deploy.py`" will actually run that file. Review what a file does before asking Forge to run it.

### The agent can make git commits

Forge can stage files and commit. These commits appear in your git history. Review with `git log` and `git diff HEAD~1` after any task involving git.

### The planner can make mistakes

The LLM planner is not perfect. Review the plan before typing `/start`. If a subtask looks wrong or dangerous, type `/task` again with a clearer description.

### Large task context

For long sessions, the context window manager compresses older conversation history. This is necessary to prevent API errors but means the agent may occasionally lose track of very early context. For critical multi-task sessions, consider restarting Forge between major tasks.

---

## Incident Recovery

**If Forge modifies something you didn't want:**
```bash
git diff          # See what changed
git checkout .    # Revert all uncommitted changes
```

**If a task gets stuck in `running` status:**
```bash
# Inside Forge
/reset
# When asked to clear task, answer y
```

**If Forge crashes and you lose context:**
Context is stored in `context/task/` and `context/project/`. These are plain Markdown files you can read directly to understand what was done.

**Checking logs:**
```bash
cat logs/errors.log    # System errors and crashes
cat logs/tasks.log     # Task completion summaries
cat logs/actions.log   # Tool calls and results
```