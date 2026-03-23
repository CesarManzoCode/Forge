"""
tasks/execution/registry.py — Registro de tools disponibles para el agente.

El LLM propone tools por nombre y argumentos en JSON.
El registry valida que existan y ejecuta la funcion correspondiente.

Uso:
    from tasks.execution.registry import registry
    result = registry.call("read_file", {"path": "src/auth.py"})
"""

import inspect
from src.tools.file import (
    read_file, read_lines, write_file, append_file,
    patch_file, create_dir, delete_dir, delete_file,
    move, find_files, grep, tree,
)
from src.tools.code import (
    run_file, run_code, run_tests, install_deps, check_env,
)
from src.tools.terminal import (
    run_command, git, curl, whitelist_info,
)
from src.tools.internet import (
    search_docs, fetch_url, fetch_github_raw, docs_sources,
)
from src.tools.system import (
    env_info, running_ports, disk_usage, get_env_var, list_env_vars,
)
from src.security import SecurityError


# ─────────────────────────────────────────────
#  TOOL DEFINITIONS
#  Cada tool tiene: funcion, descripcion, y schema de args
#  El schema se usa para validar antes de ejecutar
#  y para informar al LLM que tools existen
# ─────────────────────────────────────────────

TOOLS: dict[str, dict] = {

    # ── FILE ──
    "read_file": {
        "fn":          read_file,
        "description": "Read the full content of a file.",
        "args":        {"path": "str"},
    },
    "read_lines": {
        "fn":          read_lines,
        "description": "Read a specific line range from a file (1-indexed). Use this for large files.",
        "args":        {"path": "str", "start": "int", "end": "int"},
    },
    "write_file": {
        "fn":          write_file,
        "description": "Write content to a file. Creates parent directories if needed.",
        "args":        {"path": "str", "content": "str", "overwrite": "bool?"},
    },
    "append_file": {
        "fn":          append_file,
        "description": "Append content to the end of a file.",
        "args":        {"path": "str", "content": "str"},
    },
    "patch_file": {
        "fn":          patch_file,
        "description": (
            "Replace an exact string in a file with a new string. "
            "The 'old' string must match exactly including indentation. "
            "Fails if 'old' appears 0 or more than 1 time."
        ),
        "args":        {"path": "str", "old": "str", "new": "str"},
    },
    "create_dir": {
        "fn":          create_dir,
        "description": "Create a directory and all parent directories.",
        "args":        {"path": "str"},
    },
    "delete_file": {
        "fn":          delete_file,
        "description": "Delete a file. Requires confirmed=true — only call after user confirmed.",
        "args":        {"path": "str", "confirmed": "bool"},
    },
    "delete_dir": {
        "fn":          delete_dir,
        "description": "Delete a directory recursively. Requires confirmed=true — only call after user confirmed.",
        "args":        {"path": "str", "confirmed": "bool"},
    },
    "move": {
        "fn":          move,
        "description": "Move or rename a file or directory.",
        "args":        {"src": "str", "dst": "str"},
    },
    "find_files": {
        "fn":          find_files,
        "description": "Find files by glob pattern. Example patterns: '*.py', 'test_*.py', '**/*.json'",
        "args":        {"pattern": "str", "directory": "str?", "max_results": "int?"},
    },
    "grep": {
        "fn":          grep,
        "description": "Search for a text pattern inside files. Returns file, line_number, line_content.",
        "args":        {"pattern": "str", "directory": "str?", "extensions": "list?", "max_results": "int?"},
    },
    "tree": {
        "fn":          tree,
        "description": "Show directory structure as a tree. Ignores .git, __pycache__, node_modules.",
        "args":        {"directory": "str?", "max_depth": "int?"},
    },

    # ── CODE ──
    "run_file": {
        "fn":          run_file,
        "description": "Execute an existing Python file in the project.",
        "args":        {"path": "str", "args": "list?"},
    },
    "run_code": {
        "fn":          run_code,
        "description": "Execute a Python code snippet in an isolated sandbox.",
        "args":        {"code": "str"},
    },
    "run_tests": {
        "fn":          run_tests,
        "description": "Run pytest. Can target a file or specific test: 'tests/test_auth.py::test_login'",
        "args":        {"path": "str?", "flags": "list?"},
    },
    "install_deps": {
        "fn":          install_deps,
        "description": "Install Python dependencies with pip.",
        "args":        {"packages": "list?", "requirements_file": "str?"},
    },
    "check_env": {
        "fn":          check_env,
        "description": "Check available tool versions (python, pip, pytest).",
        "args":        {},
    },

    # ── TERMINAL ──
    "run_command": {
        "fn":          run_command,
        "description": "Run a whitelisted shell command. Check whitelist_info() to see what's allowed.",
        "args":        {"command": "str", "cwd": "str?"},
    },
    "git": {
        "fn":          git,
        "description": "Run a git command. Example: git('status') or git('log', '--oneline', '-10')",
        "args":        {"subcommand": "str", "args": "list?", "cwd": "str?"},
    },
    "curl": {
        "fn":          curl,
        "description": "Make an HTTP request with curl.",
        "args":        {"url": "str", "flags": "list?"},
    },
    "whitelist_info": {
        "fn":          whitelist_info,
        "description": "Returns the list of allowed terminal commands.",
        "args":        {},
    },

    # ── SYSTEM ──
    "env_info": {
        "fn":          env_info,
        "description": "Get environment snapshot: OS, runtimes, dev tools, venv status.",
        "args":        {},
    },
    "running_ports": {
        "fn":          running_ports,
        "description": "Check if specific ports are in use. Default checks common dev ports.",
        "args":        {"ports": "list?"},
    },
    "disk_usage": {
        "fn":          disk_usage,
        "description": "Get disk usage of the project directory in MB.",
        "args":        {"path": "str?"},
    },
    "get_env_var": {
        "fn":          get_env_var,
        "description": "Read an environment variable. Blocks sensitive keys (API keys, secrets).",
        "args":        {"key": "str"},
    },
    "list_env_vars": {
        "fn":          list_env_vars,
        "description": "List env vars with a given prefix. Default: FORGE_ config vars.",
        "args":        {"prefix": "str?"},
    },

    # ── INTERNET ──
    "search_docs": {
        "fn":          search_docs,
        "description": "Search official documentation. Sources: python, mdn, nodejs, rust, pypi, github.",
        "args":        {"query": "str", "source": "str?"},
    },
    "fetch_url": {
        "fn":          fetch_url,
        "description": "Fetch a URL and return its content as Markdown.",
        "args":        {"url": "str"},
    },
    "fetch_github_raw": {
        "fn":          fetch_github_raw,
        "description": "Read a raw file from GitHub.",
        "args":        {"owner": "str", "repo": "str", "path": "str", "branch": "str?"},
    },
    "docs_sources": {
        "fn":          docs_sources,
        "description": "Returns available documentation sources.",
        "args":        {},
    },
}


# ─────────────────────────────────────────────
#  REGISTRY CLASS
# ─────────────────────────────────────────────

class ToolRegistry:

    def call(self, tool_name: str, args: dict) -> str:
        """
        Valida y ejecuta una tool por nombre.

        El resultado siempre es string — si la tool retorna
        otro tipo, se convierte. Asi el LLM siempre recibe texto.

        Lanza:
            KeyError      — tool no existe
            TypeError     — args incorrectos
            SecurityError — operacion bloqueada por seguridad
            RuntimeError  — la tool fallo en ejecucion
        """
        if tool_name not in TOOLS:
            available = ", ".join(sorted(TOOLS.keys()))
            raise KeyError(
                f"Unknown tool: '{tool_name}'. "
                f"Available tools: {available}"
            )

        tool = TOOLS[tool_name]
        fn = tool["fn"]

        # Separar args con valor ? (opcionales) de los requeridos
        required = {
            k for k, v in tool["args"].items()
            if not v.endswith("?")
        }
        missing = required - set(args.keys())
        if missing:
            raise TypeError(
                f"Tool '{tool_name}' missing required args: {', '.join(missing)}. "
                f"Expected: {tool['args']}"
            )

        # Llamar la funcion — manejar tanto args posicionales como kwargs
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())

        # git() tiene *args — manejar especialmente
        if tool_name == "git":
            subcommand = args.get("subcommand", "")
            extra_args = args.get("args", [])
            cwd = args.get("cwd", None)
            result = fn(subcommand, *extra_args, cwd=cwd)
        elif tool_name == "curl":
            url = args.get("url", "")
            flags = args.get("flags", [])
            result = fn(url, *flags)
        else:
            # Filtrar args que la funcion acepta
            valid_args = {k: v for k, v in args.items() if k in params}
            result = fn(**valid_args)

        # Normalizar resultado a string
        if result is None:
            return "(done — no output)"
        if isinstance(result, (list, dict)):
            import json
            return json.dumps(result, indent=2, ensure_ascii=False)
        return str(result)

    def tool_list(self) -> str:
        """
        Retorna la lista de tools en formato legible para el LLM.
        Se inyecta en el system prompt del executor.
        """
        lines = []
        for name, tool in TOOLS.items():
            args_str = ", ".join(
                f"{k}: {v}" for k, v in tool["args"].items()
            )
            lines.append(f"- {name}({args_str})")
            lines.append(f"  {tool['description']}")
        return "\n".join(lines)


# Instancia global — importar esto en executor y react
registry = ToolRegistry()