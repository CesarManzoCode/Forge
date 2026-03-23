"""
tools/file/__init__.py — Operaciones de archivo para Forge.

Todas las operaciones pasan por src.security antes de ejecutarse.
El agente nunca llama a open() directamente — siempre usa estas funciones.

Uso:
    from src.tools.file import (
        read_file, write_file, patch_file,
        create_dir, delete_dir, delete_file,
        find_files, grep, tree
    )
"""

import os
import shutil
from pathlib import Path
from src.security import guard_path, guard_write, SecurityError


# ─────────────────────────────────────────────
#  READ
# ─────────────────────────────────────────────

def read_file(path: str) -> str:
    """
    Lee el contenido completo de un archivo.
    Retorna el contenido como string.
    """
    resolved = guard_path(path, operation="read")

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: '{resolved}'")
    if not resolved.is_file():
        raise IsADirectoryError(f"'{resolved}' is a directory, not a file.")

    return resolved.read_text(encoding="utf-8")


def read_lines(path: str, start: int, end: int) -> str:
    """
    Lee un rango de lineas de un archivo (1-indexed, inclusive).
    Util para que el agente inspeccione partes de archivos grandes.

    Args:
        path:  Ruta del archivo
        start: Linea inicial (1 = primera linea)
        end:   Linea final (inclusive)
    """
    resolved = guard_path(path, operation="read")

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: '{resolved}'")

    lines = resolved.read_text(encoding="utf-8").splitlines()
    total = len(lines)

    if start < 1:
        start = 1
    if end > total:
        end = total

    selected = lines[start - 1:end]
    # Devuelve con numeros de linea para que el agente pueda referenciarlos
    return "\n".join(f"{i + start:>4}  {line}" for i, line in enumerate(selected))


# ─────────────────────────────────────────────
#  WRITE
# ─────────────────────────────────────────────

def write_file(path: str, content: str, overwrite: bool = True) -> str:
    """
    Escribe contenido en un archivo.
    Crea directorios intermedios si no existen.

    Args:
        path:      Ruta del archivo
        content:   Contenido a escribir
        overwrite: Si False, lanza error si el archivo ya existe
    """
    resolved = guard_write(path, content)

    if not overwrite and resolved.exists():
        raise FileExistsError(
            f"File already exists: '{resolved}'. "
            f"Use overwrite=True to replace it."
        )

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"Written: '{resolved}' ({len(content)} chars)"


def append_file(path: str, content: str) -> str:
    """
    Agrega contenido al final de un archivo existente.
    Lo crea si no existe.
    """
    resolved = guard_write(path, content)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    with open(resolved, "a", encoding="utf-8") as f:
        f.write(content)

    return f"Appended {len(content)} chars to '{resolved}'"


# ─────────────────────────────────────────────
#  PATCH
#  Modifica lineas especificas sin reescribir todo el archivo.
#  Es la operacion mas importante para el agente — evita
#  que reescriba 500 lineas para cambiar una funcion.
# ─────────────────────────────────────────────

def patch_file(path: str, old: str, new: str) -> str:
    """
    Reemplaza la primera ocurrencia exacta de `old` con `new`.

    El agente debe pasar el fragmento exacto como aparece en el archivo,
    incluyendo indentacion y saltos de linea.

    Lanza ValueError si `old` no se encuentra o aparece mas de una vez
    (ambiguo — el agente debe ser mas especifico).
    """
    resolved = guard_path(path, operation="patch")

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: '{resolved}'")

    content = resolved.read_text(encoding="utf-8")
    count = content.count(old)

    if count == 0:
        raise ValueError(
            f"Patch failed: the target string was not found in '{resolved.name}'. "
            f"Make sure the indentation and whitespace match exactly."
        )
    if count > 1:
        raise ValueError(
            f"Patch failed: the target string appears {count} times in '{resolved.name}'. "
            f"Provide more context (more surrounding lines) to make it unambiguous."
        )

    patched = content.replace(old, new, 1)
    guard_write(path, patched)
    resolved.write_text(patched, encoding="utf-8")
    return f"Patched '{resolved.name}' — replaced {len(old)} chars with {len(new)} chars"


# ─────────────────────────────────────────────
#  DIRECTORIES
# ─────────────────────────────────────────────

def create_dir(path: str) -> str:
    """Crea un directorio y todos sus padres si no existen."""
    resolved = guard_path(path, operation="create_dir")
    resolved.mkdir(parents=True, exist_ok=True)
    return f"Directory created: '{resolved}'"


def delete_dir(path: str, confirmed: bool = False) -> str:
    """
    Elimina un directorio y todo su contenido de forma recursiva.

    REQUIERE confirmed=True — el agente debe pedir confirmacion
    explicita al usuario antes de llamar esta funcion con confirmed=True.

    Esta es la operacion mas destructiva del sistema.
    """
    if not confirmed:
        raise PermissionError(
            "delete_dir requires confirmed=True. "
            "Ask the user explicitly before deleting a directory. "
            "This operation is irreversible."
        )

    resolved = guard_path(path, operation="delete_dir")

    if not resolved.exists():
        raise FileNotFoundError(f"Directory not found: '{resolved}'")
    if not resolved.is_dir():
        raise NotADirectoryError(f"'{resolved}' is not a directory.")

    # Proteccion extra: no eliminar la raiz del proyecto
    project_root = Path(os.getenv("FORGE_PROJECT_ROOT", os.getcwd())).resolve()
    if resolved == project_root:
        raise SecurityError(
            "Security block — delete_dir denied: "
            "cannot delete the project root directory."
        )

    shutil.rmtree(resolved)
    return f"Deleted directory: '{resolved}'"


def delete_file(path: str, confirmed: bool = False) -> str:
    """
    Elimina un archivo.
    REQUIERE confirmed=True por la misma razon que delete_dir.
    """
    if not confirmed:
        raise PermissionError(
            "delete_file requires confirmed=True. "
            "Ask the user explicitly before deleting a file."
        )

    resolved = guard_path(path, operation="delete_file")

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: '{resolved}'")
    if not resolved.is_file():
        raise IsADirectoryError(f"'{resolved}' is a directory. Use delete_dir instead.")

    resolved.unlink()
    return f"Deleted file: '{resolved}'"


def move(src: str, dst: str) -> str:
    """Mueve o renombra un archivo o directorio."""
    guard_path(src, operation="move_src")
    resolved_dst = guard_path(dst, operation="move_dst")
    resolved_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, str(resolved_dst))
    return f"Moved '{src}' → '{resolved_dst}'"


# ─────────────────────────────────────────────
#  SEARCH
# ─────────────────────────────────────────────

def find_files(
    pattern: str,
    directory: str = ".",
    max_results: int = 50
) -> list[str]:
    """
    Busca archivos por patron glob dentro de un directorio.

    Args:
        pattern:     Patron glob, ej: "*.py", "test_*.py", "**/*.json"
        directory:   Directorio raiz de busqueda (default: proyecto)
        max_results: Limite de resultados para no saturar el contexto del LLM

    Retorna lista de paths relativos al proyecto.
    """
    resolved_dir = guard_path(directory, operation="find")
    project_root = Path(os.getenv("FORGE_PROJECT_ROOT", os.getcwd())).resolve()

    matches = []
    for p in sorted(resolved_dir.glob(pattern)):
        if len(matches) >= max_results:
            break
        # Retornar paths relativos — mas limpios para el LLM
        try:
            matches.append(str(p.relative_to(project_root)))
        except ValueError:
            matches.append(str(p))

    return matches


def grep(
    pattern: str,
    directory: str = ".",
    extensions: list[str] = None,
    max_results: int = 30
) -> list[dict]:
    """
    Busca un patron de texto dentro de archivos.

    Args:
        pattern:    Texto a buscar (busqueda simple, no regex)
        directory:  Directorio donde buscar
        extensions: Filtrar por extensiones, ej: [".py", ".js"]
        max_results: Limite de resultados

    Retorna lista de dicts: {file, line_number, line_content}
    """
    resolved_dir = guard_path(directory, operation="grep")
    project_root = Path(os.getenv("FORGE_PROJECT_ROOT", os.getcwd())).resolve()

    results = []
    glob_pattern = "**/*"

    for filepath in sorted(resolved_dir.glob(glob_pattern)):
        if not filepath.is_file():
            continue
        if extensions and filepath.suffix not in extensions:
            continue
        if len(results) >= max_results:
            break

        try:
            lines = filepath.read_text(encoding="utf-8", errors="ignore").splitlines()
            for i, line in enumerate(lines, start=1):
                if pattern.lower() in line.lower():
                    try:
                        rel_path = str(filepath.relative_to(project_root))
                    except ValueError:
                        rel_path = str(filepath)

                    results.append({
                        "file": rel_path,
                        "line_number": i,
                        "line_content": line.strip()
                    })

                    if len(results) >= max_results:
                        break
        except Exception:
            continue

    return results


def tree(directory: str = ".", max_depth: int = 3) -> str:
    """
    Genera una representacion de arbol del directorio.
    Ignora .git, __pycache__, node_modules, .venv automaticamente.

    Args:
        directory: Directorio raiz
        max_depth: Profundidad maxima (default 3 para no saturar el LLM)
    """
    resolved = guard_path(directory, operation="tree")

    IGNORE = {".git", "__pycache__", "node_modules", ".venv", "venv",
              ".mypy_cache", ".pytest_cache", "dist", "build", ".eggs"}

    lines = [str(resolved.name) + "/"]

    def _walk(path: Path, prefix: str, depth: int):
        if depth > max_depth:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name))
        except PermissionError:
            return

        entries = [e for e in entries if e.name not in IGNORE]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                _walk(entry, prefix + extension, depth + 1)

    _walk(resolved, "", 1)
    return "\n".join(lines)