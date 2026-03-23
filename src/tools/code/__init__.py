"""
tools/code/__init__.py — Operaciones de codigo para Forge.

Primera version: Python unicamente.
Linter y formatter se agregan en la siguiente iteracion.

Uso:
    from src.tools.code import run_file, run_code, run_tests, install_deps
"""

import subprocess
import tempfile
import os
from pathlib import Path
from src.security import guard_path, SecurityError
from src.security.config import SecurityConfig


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _get_timeout() -> int:
    return int(os.getenv("FORGE_EXEC_TIMEOUT", "30"))


def _project_root() -> Path:
    return Path(os.getenv("FORGE_PROJECT_ROOT", os.getcwd())).resolve()


def _run(
    cmd: list[str],
    cwd: str = None,
    timeout: int = None,
    env_extra: dict = None,
) -> dict:
    """
    Ejecuta un comando y retorna stdout, stderr y exit code.
    Interno — las funciones publicas deciden que retornarle al agente.
    """
    import os as _os
    env = _os.environ.copy()
    if env_extra:
        env.update(env_extra)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout or _get_timeout(),
            cwd=cwd or str(_project_root()),
            env=env,
        )
        return {
            "stdout":   result.stdout.strip(),
            "stderr":   result.stderr.strip(),
            "exit_code": result.returncode,
            "success":  result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout":   "",
            "stderr":   f"Timed out after {timeout or _get_timeout()}s.",
            "exit_code": -1,
            "success":  False,
        }
    except FileNotFoundError as e:
        return {
            "stdout":   "",
            "stderr":   f"Command not found: {e}",
            "exit_code": -1,
            "success":  False,
        }


def _format_error(result: dict, label: str) -> str:
    """Formatea el error para que el agente entienda que paso."""
    lines = [f"{label} failed (exit {result['exit_code']})"]
    if result["stderr"]:
        lines.append(result["stderr"])
    elif result["stdout"]:
        # Algunos tools mandan errores a stdout
        lines.append(result["stdout"])
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  RUN FILE
#  Ejecuta un archivo .py existente en el proyecto
# ─────────────────────────────────────────────

def run_file(path: str, args: list[str] = None) -> str:
    """
    Ejecuta un archivo Python existente en el proyecto.

    El archivo debe estar dentro del proyecto (guard_path lo verifica).
    Corre con el Python del entorno activo (venv si esta activado).

    Args:
        path: Ruta al archivo .py
        args: Argumentos opcionales para el script

    Retorna stdout si exitoso, stderr si falla.
    """
    resolved = guard_path(path, operation="run_file")

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: '{resolved}'")
    if resolved.suffix != ".py":
        raise ValueError(
            f"run_file only supports .py files. Got '{resolved.suffix}'. "
            f"Add support in FORGE_ALLOWED_EXTENSIONS if needed."
        )

    cmd = ["python", str(resolved)] + (args or [])
    result = _run(cmd, cwd=str(_project_root()))

    if result["success"]:
        return result["stdout"] or "(no output)"
    raise RuntimeError(_format_error(result, f"run_file '{resolved.name}'"))


# ─────────────────────────────────────────────
#  RUN CODE
#  Ejecuta un snippet de Python en un sandbox temporal
# ─────────────────────────────────────────────

def run_code(code: str) -> str:
    """
    Ejecuta un snippet de Python en un directorio temporal aislado.

    Usa un archivo temporal en lugar de python -c para soportar
    codigo multilinea, imports, y errores con numeros de linea correctos.

    Args:
        code: Codigo Python como string

    Retorna stdout si exitoso, stderr si falla.
    """
    sandbox_enabled = os.getenv("FORGE_SANDBOX", "true").lower() == "true"

    if not sandbox_enabled:
        raise SecurityError(
            "Security block — run_code denied: "
            "FORGE_SANDBOX is disabled. Enable it in .env to run code snippets."
        )

    with tempfile.TemporaryDirectory(prefix="forge_sandbox_") as tmpdir:
        tmp_file = Path(tmpdir) / "forge_snippet.py"
        tmp_file.write_text(code, encoding="utf-8")

        result = _run(
            ["python", str(tmp_file)],
            cwd=tmpdir,
        )

    if result["success"]:
        return result["stdout"] or "(no output)"
    raise RuntimeError(_format_error(result, "run_code"))


# ─────────────────────────────────────────────
#  RUN TESTS
#  Corre pytest en el proyecto o en un path especifico
# ─────────────────────────────────────────────

def run_tests(
    path: str = "tests",
    flags: list[str] = None,
) -> str:
    """
    Corre pytest en el proyecto.

    Maneja automaticamente el PYTHONPATH para tests en subdirectorios —
    agrega el directorio padre del test y la raiz del proyecto al path
    para que los imports funcionen sin necesidad de conftest.py manual.

    Args:
        path:  Archivo o directorio de tests (default: tests/)
               Puede ser un archivo especifico: "tests/test_auth.py"
               O un test especifico:            "tests/test_auth.py::test_login"
        flags: Flags adicionales de pytest, ej: ["-v", "-x", "--tb=short"]
               Si no se pasan, usa ["--tb=short"] por default

    Retorna el output completo de pytest.
    """
    project_root = _project_root()

    # Resolver el path del test
    if path != "tests":
        guard_path(path, operation="run_tests")

    # Construir PYTHONPATH incluyendo:
    # 1. La raiz del proyecto
    # 2. El directorio que contiene el archivo de test (para imports relativos)
    # 3. El directorio padre del test (para imports del modulo bajo test)
    python_paths = {str(project_root)}

    resolved_test_path = (project_root / path).resolve()
    if resolved_test_path.is_file():
        # Agregar el directorio del archivo de test y su padre
        python_paths.add(str(resolved_test_path.parent))
        python_paths.add(str(resolved_test_path.parent.parent))
    elif resolved_test_path.is_dir():
        # Agregar el directorio de tests y su padre
        python_paths.add(str(resolved_test_path))
        python_paths.add(str(resolved_test_path.parent))

    env_extra = {
        "PYTHONPATH": ":".join(python_paths)
    }

    default_flags = ["--tb=short", "--no-header", "-q"]
    cmd = ["python", "-m", "pytest", path] + (flags or default_flags)

    result = _run(cmd, cwd=str(project_root), env_extra=env_extra)

    # pytest retorna exit code 0 (ok), 1 (tests fallaron), 2+ (error de pytest)
    if result["exit_code"] >= 2:
        raise RuntimeError(_format_error(result, "pytest"))

    output_parts = []
    if result["stdout"]:
        output_parts.append(result["stdout"])
    if result["stderr"]:
        output_parts.append(result["stderr"])

    return "\n".join(output_parts) or "(no output from pytest)"


# ─────────────────────────────────────────────
#  INSTALL DEPS
#  Instala dependencias Python via pip
# ─────────────────────────────────────────────

def install_deps(
    packages: list[str] = None,
    requirements_file: str = None,
) -> str:
    """
    Instala dependencias Python con pip.

    Usa una de las dos formas:
        install_deps(packages=["requests", "pytest"])
        install_deps(requirements_file="requirements.txt")

    Si se pasan ambos, se instalan los dos.
    Si no se pasa ninguno, instala desde requirements.txt si existe.

    Args:
        packages:          Lista de paquetes a instalar
        requirements_file: Path a un requirements.txt

    Retorna el output de pip.
    """
    if not packages and not requirements_file:
        # Intentar requirements.txt por default
        default_req = _project_root() / "requirements.txt"
        if default_req.exists():
            requirements_file = str(default_req)
        else:
            raise ValueError(
                "install_deps requires either packages or requirements_file. "
                "No packages specified and no requirements.txt found."
            )

    results = []

    if packages:
        cmd = ["pip", "install"] + packages
        result = _run(cmd, cwd=str(_project_root()))
        if not result["success"]:
            raise RuntimeError(_format_error(result, f"pip install {' '.join(packages)}"))
        results.append(result["stdout"] or f"Installed: {', '.join(packages)}")

    if requirements_file:
        resolved = guard_path(requirements_file, operation="install_deps")
        if not resolved.exists():
            raise FileNotFoundError(f"requirements file not found: '{resolved}'")

        cmd = ["pip", "install", "-r", str(resolved)]
        result = _run(cmd, cwd=str(_project_root()))
        if not result["success"]:
            raise RuntimeError(_format_error(result, f"pip install -r {resolved.name}"))
        results.append(result["stdout"] or f"Installed from {resolved.name}")

    return "\n".join(results)


# ─────────────────────────────────────────────
#  CHECK ENV
#  Verifica que el entorno tenga lo necesario
# ─────────────────────────────────────────────

def check_env() -> dict:
    """
    Verifica las versiones de las herramientas disponibles.
    Util para que el agente sepa con que puede contar.

    Retorna dict con versiones o None si no esta instalado.
    """
    tools = {
        "python":  ["python", "--version"],
        "pip":     ["pip",    "--version"],
        "pytest":  ["python", "-m", "pytest", "--version"],
    }

    env_info = {}
    for name, cmd in tools.items():
        result = _run(cmd)
        if result["success"]:
            # Primera linea del output, limpia
            output = (result["stdout"] or result["stderr"]).splitlines()
            env_info[name] = output[0] if output else "available"
        else:
            env_info[name] = None

    return env_info