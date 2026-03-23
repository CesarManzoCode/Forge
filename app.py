"""
app.py — Punto de entrada de Forge.
Corre desde la raiz del proyecto:

    python app.py
    python app.py --dev
"""

import sys
import os
import argparse
from dotenv import load_dotenv

# ─────────────────────────────────────────────
#  BOOTSTRAP
#  Asegura que la raiz del proyecto este en
#  sys.path para que todos los imports funcionen
#  sin importar desde donde se corra el script.
# ─────────────────────────────────────────────

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Cargar .env antes de importar cualquier modulo
# que lea variables de entorno en su nivel de modulo
load_dotenv(os.path.join(ROOT, ".env"))


# ─────────────────────────────────────────────
#  ARGS
#  --dev sobreescribe DEV_MODE del .env
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        prog="forge",
        description="Forge — AI Agent for Developers"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable developer mode (overrides .env DEV_MODE)"
    )
    return parser.parse_args()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

def main():
    args = parse_args()

    # --dev flag sobreescribe lo que diga el .env
    if args.dev:
        os.environ["DEV_MODE"] = "true"

    # Importar despues del bootstrap para que
    # sys.path y .env ya esten listos
    from interface.cli.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()