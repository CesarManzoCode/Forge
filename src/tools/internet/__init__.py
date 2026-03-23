"""
tools/internet/__init__.py — Herramientas de internet para Forge.

Enfocado exclusivamente en uso tecnico:
- Buscar en documentacion oficial de lenguajes y frameworks
- Leer archivos raw de GitHub

No es para busqueda general. El agente busca porque tiene un error
o necesita entender una API, no para explorar temas random.

Dependencias:
    pip install requests beautifulsoup4 html2text

Uso:
    from src.tools.internet import search_docs, fetch_github_raw
"""

import os
import re
import requests
from urllib.parse import urljoin, urlparse, quote_plus

# html2text convierte HTML a Markdown legible
# beautifulsoup4 para extraer el contenido relevante antes de convertir
try:
    import html2text
    import bs4
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

DEFAULT_TIMEOUT = int(os.getenv("FORGE_HTTP_TIMEOUT", "15"))
MAX_CONTENT_CHARS = int(os.getenv("FORGE_MAX_CONTENT_CHARS", "12000"))

HEADERS = {
    "User-Agent": "Forge-Agent/1.0 (developer tool; not a crawler)",
}

# ─────────────────────────────────────────────
#  DOCUMENTACION OFICIAL — fuentes conocidas
#  El agente elige la fuente correcta segun el tema
# ─────────────────────────────────────────────

DOCS_SOURCES: dict[str, dict] = {
    # Python
    "python": {
        "search_url": "https://docs.python.org/3/search.html?q={query}",
        "base_url":   "https://docs.python.org/3/",
        "description": "Python 3 official documentation",
    },
    # JavaScript / Web
    "mdn": {
        "search_url": "https://developer.mozilla.org/en-US/search?q={query}",
        "base_url":   "https://developer.mozilla.org/",
        "description": "MDN Web Docs — JS, HTML, CSS, Web APIs",
    },
    # Node.js
    "nodejs": {
        "search_url": "https://nodejs.org/en/search/?query={query}",
        "base_url":   "https://nodejs.org/",
        "description": "Node.js official documentation",
    },
    # Rust
    "rust": {
        "search_url": "https://doc.rust-lang.org/std/?search={query}",
        "base_url":   "https://doc.rust-lang.org/",
        "description": "Rust standard library docs",
    },
    # PyPI — buscar paquetes
    "pypi": {
        "search_url": "https://pypi.org/search/?q={query}",
        "base_url":   "https://pypi.org/",
        "description": "Python Package Index",
    },
    # GitHub
    "github": {
        "search_url": "https://github.com/search?q={query}&type=repositories",
        "base_url":   "https://github.com/",
        "description": "GitHub repository search",
    },
}


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _check_deps():
    if not _DEPS_AVAILABLE:
        raise ImportError(
            "tools/internet requires additional dependencies.\n"
            "Run: pip install requests beautifulsoup4 html2text"
        )


def _fetch_raw(url: str) -> str:
    """Hace el HTTP GET y retorna el texto crudo. Maneja errores comunes."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Request timed out after {DEFAULT_TIMEOUT}s: '{url}'. "
            f"Increase FORGE_HTTP_TIMEOUT in .env if needed."
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"HTTP error fetching '{url}': {e.response.status_code} {e.response.reason}"
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Could not connect to '{url}'. Check your internet connection."
        )


def _html_to_markdown(html: str, base_url: str = "") -> str:
    """
    Convierte HTML a Markdown legible para el LLM.

    Estrategia:
    1. BeautifulSoup extrae el contenido principal (article, main, .content)
       eliminando nav, header, footer, sidebars — ruido para el LLM
    2. html2text convierte el HTML limpio a Markdown
    3. Se trunca a MAX_CONTENT_CHARS para no saturar el contexto
    """
    soup = bs4.BeautifulSoup(html, "html.parser")

    # Eliminar elementos que no aportan contenido al LLM
    for tag in soup.find_all(["nav", "header", "footer", "script",
                               "style", "aside", "form", "iframe"]):
        tag.decompose()

    # Intentar extraer el contenido principal en orden de preferencia
    main_content = (
        soup.find("article") or
        soup.find("main") or
        soup.find(attrs={"class": re.compile(r"content|main|body|docs", re.I)}) or
        soup.find("body") or
        soup
    )

    converter = html2text.HTML2Text()
    converter.baseurl = base_url
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.body_width = 0        # Sin wrap de lineas
    converter.protect_links = True
    converter.unicode_snob = True

    markdown = converter.handle(str(main_content))

    # Limpiar lineas en blanco excesivas
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()

    # Truncar si es muy largo
    if len(markdown) > MAX_CONTENT_CHARS:
        markdown = markdown[:MAX_CONTENT_CHARS]
        markdown += (
            f"\n\n[ content truncated at {MAX_CONTENT_CHARS} chars. "
            f"Set FORGE_MAX_CONTENT_CHARS in .env to increase. ]"
        )

    return markdown


# ─────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────

def search_docs(query: str, source: str = "python") -> str:
    """
    Busca en la documentacion oficial de una fuente conocida
    y retorna el contenido de la pagina de resultados en Markdown.

    El agente recibe los resultados de busqueda formateados — puede
    entonces llamar a fetch_url() con un link especifico si necesita
    leer una pagina en detalle.

    Args:
        query:  Termino a buscar, ej: "pathlib read_text", "async/await"
        source: Fuente de documentacion. Opciones:
                python, mdn, nodejs, rust, pypi, github

    Retorna el contenido de la pagina de resultados en Markdown.
    """
    _check_deps()

    source = source.lower().strip()
    if source not in DOCS_SOURCES:
        available = ", ".join(DOCS_SOURCES.keys())
        raise ValueError(
            f"Unknown docs source: '{source}'. "
            f"Available: {available}"
        )

    src = DOCS_SOURCES[source]
    url = src["search_url"].format(query=quote_plus(query))

    html = _fetch_raw(url)
    markdown = _html_to_markdown(html, base_url=src["base_url"])

    header = (
        f"# Search results: '{query}' in {src['description']}\n"
        f"Source: {url}\n\n"
    )

    return header + markdown


def fetch_url(url: str) -> str:
    """
    Descarga y convierte a Markdown el contenido de cualquier URL.

    Uso principal: leer una pagina especifica de documentacion
    despues de encontrarla con search_docs().

    Args:
        url: URL completa a leer

    Retorna el contenido en Markdown.
    """
    _check_deps()

    parsed = urlparse(url)
    if not parsed.scheme in ("http", "https"):
        raise ValueError(
            f"Invalid URL scheme: '{parsed.scheme}'. "
            f"Only http and https are supported."
        )

    html = _fetch_raw(url)
    markdown = _html_to_markdown(html, base_url=f"{parsed.scheme}://{parsed.netloc}")

    header = f"# {url}\n\n"
    return header + markdown


def fetch_github_raw(
    owner: str,
    repo: str,
    path: str,
    branch: str = "main",
) -> str:
    """
    Lee un archivo raw de GitHub sin convertir — util para leer
    codigo fuente, READMEs, configs, y specs directamente.

    Args:
        owner:  Usuario u organizacion, ej: "psf"
        repo:   Nombre del repositorio, ej: "requests"
        path:   Ruta al archivo dentro del repo, ej: "README.md"
        branch: Rama (default: "main", prueba "master" si falla)

    Retorna el contenido raw del archivo como string.
    """
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    try:
        content = _fetch_raw(url)
    except RuntimeError as e:
        # Si falla con main, sugerir master
        if branch == "main" and "404" in str(e):
            raise RuntimeError(
                f"{e}\n"
                f"Tip: the repository might use 'master' as the default branch. "
                f"Try fetch_github_raw('{owner}', '{repo}', '{path}', branch='master')"
            )
        raise

    # Truncar si es muy largo (archivos grandes de codigo)
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS]
        content += (
            f"\n\n[ file truncated at {MAX_CONTENT_CHARS} chars ]"
        )

    header = f"# {owner}/{repo}/{path} @ {branch}\n\n"
    return header + content


def docs_sources() -> dict:
    """
    Retorna las fuentes de documentacion disponibles.
    El agente puede llamar esto para saber donde buscar.
    """
    return {
        key: val["description"]
        for key, val in DOCS_SOURCES.items()
    }