"""
tools/system/__init__.py — Informacion del entorno del desarrollador.

Enfocado en lo que un agente necesita saber antes de ejecutar tareas:
versiones de herramientas, procesos activos, disco, variables de entorno.

Uso:
    from src.tools.system import env_info, running_ports, disk_usage, get_env_var
"""

import os
import subprocess
import shutil
import socket
from pathlib import Path


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _run(cmd: list[str]) -> str:
    """Ejecuta un comando y retorna stdout. Silencioso si falla."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception:
        return None


def _version(cmd: list[str]) -> str | None:
    """Retorna la primera linea del output de un comando --version."""
    out = _run(cmd)
    if out:
        return out.splitlines()[0]
    return None


# ─────────────────────────────────────────────
#  ENV INFO
#  Lo mas util: que herramientas hay disponibles
# ─────────────────────────────────────────────

def env_info() -> dict:
    """
    Retorna un snapshot del entorno de desarrollo actual.

    Incluye: OS, shell, versiones de runtimes y herramientas comunes,
    directorio del proyecto, y si hay un venv activo.

    El agente debe llamar esto al inicio de tareas que dependan
    del entorno — instalacion de deps, ejecucion de tests, etc.
    """
    project_root = Path(os.getenv("FORGE_PROJECT_ROOT", os.getcwd()))

    # Detectar venv activo
    venv = os.getenv("VIRTUAL_ENV")
    venv_active = bool(venv)
    venv_path = Path(venv).name if venv else None

    # Runtimes
    runtimes = {}
    runtime_cmds = {
        "python":  ["python", "--version"],
        "node":    ["node",   "--version"],
        "npm":     ["npm",    "--version"],
        "go":      ["go",     "version"],
        "rust":    ["rustc",  "--version"],
        "java":    ["java",   "--version"],
    }
    for name, cmd in runtime_cmds.items():
        v = _version(cmd)
        if v:
            runtimes[name] = v

    # Herramientas de desarrollo
    dev_tools = {}
    tool_cmds = {
        "git":     ["git",    "--version"],
        "docker":  ["docker", "--version"],
        "make":    ["make",   "--version"],
        "pip":     ["pip",    "--version"],
        "pytest":  ["python", "-m", "pytest", "--version"],
        "ruff":    ["ruff",   "--version"],
        "black":   ["black",  "--version"],
    }
    for name, cmd in tool_cmds.items():
        v = _version(cmd)
        if v:
            dev_tools[name] = v

    return {
        "os":           _run(["uname", "-sr"]),
        "shell":        os.getenv("SHELL", "unknown"),
        "project_root": str(project_root),
        "venv_active":  venv_active,
        "venv_name":    venv_path,
        "runtimes":     runtimes,
        "dev_tools":    dev_tools,
    }


# ─────────────────────────────────────────────
#  RUNNING PORTS
#  Saber si un servidor ya esta corriendo
# ─────────────────────────────────────────────

def running_ports(ports: list[int] = None) -> dict[int, bool]:
    """
    Verifica si puertos especificos estan en uso.

    Util para saber si un servidor de desarrollo ya esta activo
    antes de intentar levantarlo de nuevo.

    Args:
        ports: Lista de puertos a verificar.
               Default: puertos comunes de desarrollo.

    Retorna dict {puerto: ocupado}
    """
    if ports is None:
        ports = [3000, 4000, 5000, 5173, 8000, 8080, 8888, 9000]

    result = {}
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            occupied = s.connect_ex(("127.0.0.1", port)) == 0
            result[port] = occupied

    return result


# ─────────────────────────────────────────────
#  DISK USAGE
#  Antes de escribir archivos grandes
# ─────────────────────────────────────────────

def disk_usage(path: str = None) -> dict:
    """
    Retorna el uso de disco del directorio del proyecto.

    Util antes de operaciones que generen muchos archivos
    o instalen dependencias pesadas.

    Args:
        path: Directorio a medir. Default: project root.

    Retorna total, used, free en MB y porcentaje usado.
    """
    target = path or os.getenv("FORGE_PROJECT_ROOT", os.getcwd())
    usage = shutil.disk_usage(target)

    def to_mb(b: int) -> float:
        return round(b / 1024 / 1024, 1)

    return {
        "path":         target,
        "total_mb":     to_mb(usage.total),
        "used_mb":      to_mb(usage.used),
        "free_mb":      to_mb(usage.free),
        "used_percent": round(usage.used / usage.total * 100, 1),
    }


# ─────────────────────────────────────────────
#  ENV VARS
#  Leer variables de entorno sin exponer secretos
# ─────────────────────────────────────────────

# Variables que NUNCA se deben exponer al LLM
_SENSITIVE_KEYS = {
    "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "DATABASE_URL", "SECRET_KEY", "JWT_SECRET",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "GITHUB_TOKEN", "NPM_TOKEN", "PYPI_TOKEN",
    "PASSWORD", "PASSWD", "PASS", "TOKEN", "API_KEY",
    "PRIVATE_KEY", "CERT", "SSL",
}


def get_env_var(key: str) -> str:
    """
    Lee una variable de entorno.
    Bloquea variables sensibles — el LLM nunca debe ver secrets.

    Args:
        key: Nombre de la variable

    Retorna el valor o None si no existe.
    Lanza PermissionError si la variable es sensible.
    """
    key_upper = key.upper()

    # Verificar contra lista de sensibles y patrones
    if key_upper in _SENSITIVE_KEYS:
        raise PermissionError(
            f"get_env_var blocked: '{key}' is a sensitive variable. "
            f"Forge does not expose secrets to the agent."
        )

    for sensitive in _SENSITIVE_KEYS:
        if sensitive in key_upper:
            raise PermissionError(
                f"get_env_var blocked: '{key}' matches sensitive pattern '{sensitive}'. "
                f"Forge does not expose secrets to the agent."
            )

    value = os.getenv(key)
    if value is None:
        return f"Variable '{key}' is not set."
    return value


def list_env_vars(prefix: str = "FORGE_") -> dict[str, str]:
    """
    Lista variables de entorno con un prefijo especifico.
    Util para que el agente vea la configuracion de Forge.
    Solo muestra variables con el prefijo dado — nunca el entorno completo.

    Args:
        prefix: Prefijo a filtrar. Default: "FORGE_"
    """
    result = {}
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        # Enmascarar si parece sensible
        is_sensitive = any(s in key.upper() for s in _SENSITIVE_KEYS)
        result[key] = "***" if is_sensitive else value
    return result