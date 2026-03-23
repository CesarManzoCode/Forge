"""
guards.py — Funciones de seguridad reutilizables de Forge.

Uso directo:
    from src.security.guards import guard_path, guard_exec

Como decorador:
    from src.security.guards import require_safe_path

    @require_safe_path(arg_index=0)
    def read_file(path: str) -> str:
        ...
"""

import os
import subprocess
import tempfile
import functools
from pathlib import Path
from src.security.config import SecurityConfig


# ─────────────────────────────────────────────
#  EXCEPTION
# ─────────────────────────────────────────────

class SecurityError(Exception):
    """Se lanza cuando una operacion viola las reglas de seguridad.
    El mensaje describe el motivo exacto para que el agente pueda reportarlo.
    """
    pass


# ─────────────────────────────────────────────
#  SHARED CONFIG INSTANCE
#  Una sola instancia por proceso
# ─────────────────────────────────────────────

_cfg = SecurityConfig()


# ─────────────────────────────────────────────
#  PATH GUARD
# ─────────────────────────────────────────────

def guard_path(path: str, operation: str = "access") -> Path:
    """
    Valida que un path sea seguro para operar.

    - Resuelve el path a absoluto para evitar directory traversal (../../etc)
    - Verifica que este dentro del proyecto
    - Verifica que no sea un archivo/directorio bloqueado

    Retorna el Path resuelto si es valido.
    Lanza SecurityError con motivo si no lo es.

    Args:
        path: El path a validar (relativo o absoluto)
        operation: Descripcion de la operacion para el mensaje de error
    """
    raw = Path(path)
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        resolved = (_cfg.project_root / raw).resolve()

    # Verificar que este dentro del proyecto
    try:
        resolved.relative_to(_cfg.project_root)
    except ValueError:
        raise SecurityError(
            f"Security block — {operation} denied: "
            f"'{resolved}' is outside the project root '{_cfg.project_root}'. "
            f"Forge can only operate within the project directory."
        )

    # Verificar rutas absolutas bloqueadas (por si acaso project_root
    # estuviera mal configurado)
    for blocked in SecurityConfig.BLOCKED_ABSOLUTE:
        if str(resolved).startswith(blocked):
            raise SecurityError(
                f"Security block — {operation} denied: "
                f"'{resolved}' is a protected system path."
            )

    # Verificar nombres de archivo bloqueados
    for blocked_name in SecurityConfig.BLOCKED_FILENAMES:
        if resolved.name == blocked_name or blocked_name in resolved.parts:
            raise SecurityError(
                f"Security block — {operation} denied: "
                f"'{resolved.name}' is a protected filename."
            )

    return resolved


def guard_write(path: str, content: str | bytes) -> Path:
    """
    Valida path y tamaño antes de escribir un archivo.
    Extiende guard_path con la verificacion de bytes.
    """
    resolved = guard_path(path, operation="write")

    size = len(content.encode() if isinstance(content, str) else content)
    if size > _cfg.max_write_bytes:
        raise SecurityError(
            f"Security block — write denied: "
            f"content size ({size} bytes) exceeds limit "
            f"({_cfg.max_write_bytes} bytes). "
            f"Split the content into smaller writes."
        )

    return resolved


# ─────────────────────────────────────────────
#  EXEC GUARD
# ─────────────────────────────────────────────

def guard_exec(code: str, language: str) -> str:
    """
    Ejecuta codigo en un entorno controlado.

    - Verifica que el lenguaje este en la lista de extensiones permitidas
    - Si sandbox esta activo, corre en un directorio temporal aislado
    - Aplica timeout configurable
    - Captura stdout y stderr

    Retorna el output como string.
    Lanza SecurityError si el lenguaje no esta permitido.
    Lanza RuntimeError si el codigo falla (con el stderr incluido).

    Args:
        code: El codigo a ejecutar
        language: Extension del lenguaje, ej: ".py", ".js"
    """
    if not _cfg.sandbox_enabled:
        raise SecurityError(
            "Security block — exec denied: "
            "sandbox is disabled (FORGE_SANDBOX=false). "
            "Enable it in .env to allow code execution."
        )

    # Normalizar extension
    ext = language if language.startswith(".") else f".{language}"

    if ext in SecurityConfig.BLOCKED_EXEC_EXTENSIONS:
        raise SecurityError(
            f"Security block — exec denied: "
            f"'{ext}' files cannot be executed directly. "
            f"Use tools/terminal for shell scripts."
        )

    if ext not in _cfg.allowed_extensions:
        raise SecurityError(
            f"Security block — exec denied: "
            f"'{ext}' is not in the allowed extensions list. "
            f"Allowed: {', '.join(_cfg.allowed_extensions)}. "
            f"Add it to FORGE_ALLOWED_EXTENSIONS in .env to enable."
        )

    # Comandos de ejecucion por lenguaje
    runners = {
        ".py":   ["python", "-c", code],
        ".js":   ["node",   "-e", code],
        ".ts":   ["npx",    "ts-node", "-e", code],
        ".rb":   ["ruby",   "-e", code],
    }

    # Para lenguajes que no soportan -e, escribir a archivo temporal
    file_runners = {
        ".go":   lambda f: ["go", "run", f],
        ".rs":   lambda f: ["rustc", f, "-o", f + ".out", "&&", f + ".out"],
        ".java": lambda f: ["java", f],
    }

    # Directorio de ejecucion: temporal si sandbox, raiz si no
    exec_dir = tempfile.mkdtemp(prefix="forge_sandbox_") if _cfg.sandbox_enabled else str(_cfg.project_root)

    try:
        if ext in runners:
            cmd = runners[ext]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_cfg.exec_timeout,
                cwd=exec_dir,
            )
        elif ext in file_runners:
            # Escribir a archivo temporal
            tmp_file = os.path.join(exec_dir, f"forge_exec{ext}")
            with open(tmp_file, "w") as f:
                f.write(code)
            cmd = file_runners[ext](tmp_file)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_cfg.exec_timeout,
                cwd=exec_dir,
                shell=isinstance(cmd, str),
            )
        else:
            raise SecurityError(
                f"Security block — exec denied: "
                f"no runner configured for '{ext}'."
            )

        if result.returncode != 0:
            raise RuntimeError(
                f"Execution failed (exit {result.returncode}):\n"
                f"{result.stderr.strip()}"
            )

        return result.stdout

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Execution timed out after {_cfg.exec_timeout}s. "
            f"Increase FORGE_EXEC_TIMEOUT in .env if needed."
        )


# ─────────────────────────────────────────────
#  DECORATORS
#  Para aplicar guards a funciones de tools/
# ─────────────────────────────────────────────

def require_safe_path(arg_index: int = 0, operation: str = "access"):
    """
    Decorador que valida el path en la posicion arg_index
    antes de ejecutar la funcion.

    Uso:
        @require_safe_path(arg_index=0, operation="read")
        def read_file(path: str) -> str:
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if arg_index < len(args):
                guard_path(str(args[arg_index]), operation=operation)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_safe_write(path_index: int = 0, content_index: int = 1):
    """
    Decorador que valida path y tamaño de contenido antes de escribir.

    Uso:
        @require_safe_write(path_index=0, content_index=1)
        def write_file(path: str, content: str) -> None:
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            path = str(args[path_index]) if path_index < len(args) else kwargs.get("path", "")
            content = args[content_index] if content_index < len(args) else kwargs.get("content", "")
            guard_write(path, content)
            return func(*args, **kwargs)
        return wrapper
    return decorator