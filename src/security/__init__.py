"""
src/security/__init__.py

Exporta la API publica de seguridad.
Cualquier tool importa desde aqui, no directamente de guards o config.

Uso:
    from src.security import guard_path, guard_write, guard_exec
    from src.security import require_safe_path, require_safe_write
    from src.security import SecurityError
"""

from src.security.guards import (
    guard_path,
    guard_write,
    guard_exec,
    require_safe_path,
    require_safe_write,
    SecurityError,
)

from src.security.config import SecurityConfig

__all__ = [
    "guard_path",
    "guard_write",
    "guard_exec",
    "require_safe_path",
    "require_safe_write",
    "SecurityError",
    "SecurityConfig",
]