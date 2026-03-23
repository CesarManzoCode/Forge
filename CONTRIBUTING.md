# Contributing to Forge

Thank you for your interest in contributing to Forge. This document explains how to get started, what areas need help, and what standards to follow.

---

## Getting Started

```bash
git clone https://github.com/youruser/forge.git
cd forge
python -m venv venv
source venv/bin/activate
pip install groq python-dotenv tiktoken requests beautifulsoup4 html2text pytest
cp .env.example .env
# Add your GROQ_API_KEY to .env
```

Run the test suite to verify your setup:

```bash
pytest tests/
```

---

## Areas Open for Contribution

### High Priority

- **New tools** — `src/tools/` is modular. Adding a new tool requires implementing the functions and registering them in `tasks/execution/registry.py`. See the existing tools for reference.
- **Language support** — `FORGE_LANGUAGE` currently works via prompt injection. Native multi-language planning prompts would improve consistency.
- **Windows compatibility** — `src/security/config.py` has Linux-specific blocked paths. A Windows-aware config layer would allow cross-platform use.
- **Web interface** — The CLI (`interface/cli/`) is the only interface. A web interface would open Forge to a wider audience.

### Medium Priority

- **More LLM providers** — `llm/ai.py` currently uses Groq only. Abstracting the provider would allow OpenAI, Anthropic, Ollama, etc.
- **Richer memory** — `memory/user.json` is currently a simple key-value store. A vector-based memory system would improve long-term personalization.
- **Task history** — Completed tasks are summarized in `context/project/`. A proper task history browser would help users track past work.

### Low Priority / Good First Issues

- Additional git subcommands in the terminal whitelist
- More documentation sources in `tools/internet/`
- Improving planner prompts for specific task types

---

## Code Standards

### Structure

Every new tool module should live in `src/tools/<name>/__init__.py` and follow this pattern:

```python
from src.security import guard_path, SecurityError

def my_function(path: str) -> str:
    """
    One-line description.

    Args:
        path: Description of the argument.

    Returns:
        Description of what is returned.

    Raises:
        SecurityError: If the path violates security rules.
        FileNotFoundError: If the file does not exist.
    """
    resolved = guard_path(path, operation="my_function")
    # implementation
    return result
```

Every new tool must be registered in `tasks/execution/registry.py` with a name, description, and args schema.

### Security

All file operations must go through `guard_path()` or `guard_write()` from `src/security/`. Never call `open()` directly on user-provided paths.

All shell commands must go through the whitelist in `src/tools/terminal/__init__.py`. Never call `subprocess` directly with user-provided strings.

### Prompts

All LLM prompts live in `llm/prompts.py`. Do not put prompt strings inline in other modules. If you add a new interaction pattern, add a corresponding class or method to `prompts.py`.

### Testing

- Place tests in `tests/`
- Test file naming: `test_<module_name>.py`
- Each public function should have at least one test covering the happy path and one covering an error case

---

## Pull Request Process

1. Fork the repository and create a branch: `git checkout -b feat/your-feature`
2. Make your changes following the code standards above
3. Add or update tests as needed
4. Update documentation in `docs/` if your change affects user-facing behavior or module interfaces
5. Open a pull request with a clear description of what changed and why

### Commit Message Format

```
type: short description

Optional longer explanation.
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Examples:
```
feat: add Docker tool to tools/terminal
fix: handle empty task.json gracefully in executor
docs: add Windows compatibility notes to dev guide
```

---

## Reporting Issues

When reporting a bug, please include:

- Your OS and Python version
- The contents of your `.env` (with API key redacted)
- The exact error message and traceback from `logs/errors.log`
- What you were trying to do when the error occurred

---

## Questions

Open an issue with the `question` label. We try to respond within a few days.