"""
tools/terminal/__init__.py — Ejecucion controlada de comandos shell.

Solo comandos en la whitelist pueden ejecutarse.
La whitelist tiene defaults seguros y es ampliable via .env.

Uso:
    from src.tools.terminal import run_command, git, curl
"""

import subprocess
import os
import shlex
from pathlib import Path


# ─────────────────────────────────────────────
#  WHITELIST
#  Comandos base permitidos por default.
#  Formato: "comando": [subcomandos permitidos] o None para cualquiera
# ─────────────────────────────────────────────

BASE_WHITELIST: dict[str, list[str] | None] = {
    # git — solo operaciones de lectura y stage/commit seguras
    "git": [
        "status", "log", "diff", "add", "commit",
        "branch", "checkout", "stash", "show",
        "remote", "fetch", "pull", "push",
        "init", "clone", "merge", "rebase",
        "tag", "blame", "shortlog",
    ],
    # curl — HTTP requests
    "curl": None,   # cualquier flag de curl permitido
    "wget": None,
}

# Comandos bloqueados aunque aparezcan en whitelist ampliada
# Estos nunca se ejecutan sin importar la configuracion
HARD_BLOCKED = {
    "rm", "rmdir", "dd", "mkfs", "fdisk",
    "sudo", "su", "chmod", "chown",
    "systemctl", "service",
    "iptables", "ufw",
    "passwd", "useradd", "userdel",
    "crontab", "at",
    "nc", "netcat", "ncat",
    "python", "python3", "node", "bash", "sh", "zsh",
    # python/node/bash se manejan via tools/code y tools/terminal.run_command
    # con validacion propia — no via shell directo
}


def _load_whitelist() -> dict[str, list[str] | None]:
    """
    Carga la whitelist base mas los comandos extra del .env.

    FORGE_EXTRA_COMMANDS=make,cargo,go
    Agrega esos comandos con subcomandos libres (None).
    """
    whitelist = dict(BASE_WHITELIST)

    extra = os.getenv("FORGE_EXTRA_COMMANDS", "")
    for cmd in extra.split(","):
        cmd = cmd.strip()
        if cmd and cmd not in HARD_BLOCKED:
            whitelist[cmd] = None

    return whitelist


def _get_timeout() -> int:
    return int(os.getenv("FORGE_EXEC_TIMEOUT", "30"))


def _project_root() -> Path:
    return Path(os.getenv("FORGE_PROJECT_ROOT", os.getcwd())).resolve()


def _get_max_lines() -> int:
    return int(os.getenv("FORGE_TERMINAL_MAX_LINES", "200"))


# ─────────────────────────────────────────────
#  VALIDATION
# ─────────────────────────────────────────────

class CommandBlockedError(Exception):
    """Se lanza cuando un comando no esta en la whitelist."""
    pass


def _validate(cmd_parts: list[str]) -> None:
    """
    Valida que el comando este permitido.

    Reglas:
    1. El binario principal debe estar en la whitelist
    2. No puede estar en HARD_BLOCKED
    3. Si el comando tiene subcomandos restringidos,
       el primer argumento debe estar en esa lista
    """
    if not cmd_parts:
        raise ValueError("Empty command.")

    binary = cmd_parts[0].strip()

    if binary in HARD_BLOCKED:
        raise CommandBlockedError(
            f"Command blocked: '{binary}' is in the permanent blocklist. "
            f"Use the appropriate Forge tool instead "
            f"(tools/code for python/node, tools/file for file operations)."
        )

    whitelist = _load_whitelist()

    if binary not in whitelist:
        allowed = ", ".join(sorted(whitelist.keys()))
        raise CommandBlockedError(
            f"Command blocked: '{binary}' is not in the whitelist. "
            f"Allowed commands: {allowed}. "
            f"Add it to FORGE_EXTRA_COMMANDS in .env to enable it."
        )

    allowed_subs = whitelist[binary]
    if allowed_subs is not None and len(cmd_parts) > 1:
        subcommand = cmd_parts[1]
        if subcommand.startswith("-"):
            # Es un flag, no un subcomando — permitir
            return
        if subcommand not in allowed_subs:
            raise CommandBlockedError(
                f"Command blocked: '{binary} {subcommand}' is not allowed. "
                f"Allowed subcommands for '{binary}': {', '.join(allowed_subs)}."
            )


# ─────────────────────────────────────────────
#  CORE RUNNER
# ─────────────────────────────────────────────

def _run(
    cmd_parts: list[str],
    cwd: str = None,
    env_extra: dict = None,
) -> str:
    """
    Ejecuta el comando y retorna el output completo.
    stdout y stderr se combinan en orden cronologico.
    """
    timeout = _get_timeout()
    max_lines = _get_max_lines()
    work_dir = cwd or str(_project_root())

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    try:
        result = subprocess.run(
            cmd_parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            text=True,
            timeout=timeout,
            cwd=work_dir,
            env=env,
        )

        output = result.stdout.strip()

        # Limitar lineas para no saturar el contexto del LLM
        lines = output.splitlines()
        truncated = False
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True

        final_output = "\n".join(lines)

        if truncated:
            final_output += (
                f"\n\n[ output truncated — showing {max_lines} of "
                f"{len(output.splitlines())} lines. "
                f"Set FORGE_TERMINAL_MAX_LINES in .env to increase. ]"
            )

        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed (exit {result.returncode}):\n{final_output}"
            )

        return final_output or "(no output)"

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Command timed out after {timeout}s: '{' '.join(cmd_parts)}'"
        )
    except FileNotFoundError:
        raise CommandBlockedError(
            f"Command not found: '{cmd_parts[0]}'. "
            f"Make sure it is installed on the system."
        )


# ─────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────

def run_command(command: str, cwd: str = None) -> str:
    """
    Ejecuta un comando shell validado contra la whitelist.

    El comando se parsea con shlex para manejar correctamente
    strings con espacios, comillas, etc.

    Args:
        command: Comando como string, ej: "git status"
                 o "curl -s https://api.github.com/repos/user/repo"
        cwd:     Directorio de ejecucion (default: raiz del proyecto)

    Retorna el output completo como string.
    Lanza CommandBlockedError si el comando no esta permitido.
    Lanza RuntimeError si el comando falla.
    """
    try:
        cmd_parts = shlex.split(command)
    except ValueError as e:
        raise ValueError(f"Could not parse command '{command}': {e}")

    _validate(cmd_parts)
    return _run(cmd_parts, cwd=cwd)


# ─────────────────────────────────────────────
#  SHORTCUTS
#  Wrappers tipados para los comandos mas usados.
#  El agente los puede llamar directamente sin
#  construir strings de comando manualmente.
# ─────────────────────────────────────────────

def git(subcommand: str, *args: str, cwd: str = None) -> str:
    """
    Ejecuta un comando git.

    Uso:
        git("status")
        git("log", "--oneline", "-10")
        git("add", "src/tools/file/__init__.py")
        git("commit", "-m", "feat: add file tools")
        git("diff", "HEAD~1")

    Args:
        subcommand: Subcomando git (status, log, diff, etc)
        *args:      Argumentos adicionales
        cwd:        Directorio (default: raiz del proyecto)
    """
    cmd_parts = ["git", subcommand] + list(args)
    _validate(cmd_parts)
    return _run(cmd_parts, cwd=cwd)


def curl(url: str, *flags: str) -> str:
    """
    Ejecuta curl para hacer HTTP requests.

    Uso:
        curl("https://api.github.com/repos/user/repo")
        curl("https://pypi.org/pypi/requests/json", "-s")
        curl("https://example.com", "-H", "Accept: application/json")

    Args:
        url:    URL a llamar
        *flags: Flags adicionales de curl
    """
    cmd_parts = ["curl"] + list(flags) + [url]
    _validate(cmd_parts)
    return _run(cmd_parts)


def whitelist_info() -> dict:
    """
    Retorna la whitelist activa con sus subcomandos.
    Util para que el agente sepa que puede ejecutar.
    """
    wl = _load_whitelist()
    return {
        cmd: subs if subs else "all subcommands allowed"
        for cmd, subs in wl.items()
    }