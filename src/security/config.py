"""
config.py — Reglas de seguridad de Forge.

Reglas FIJAS: nunca cambian, hardcodeadas.
Reglas CONFIGURABLES: se leen del .env, tienen defaults seguros.

Uso:
    from src.security.config import SecurityConfig
    cfg = SecurityConfig()
"""

import os
from pathlib import Path


class SecurityConfig:

    # ─────────────────────────────────────────
    #  FIXED RULES — no cambian nunca
    # ─────────────────────────────────────────

    # Rutas absolutas que jamas se pueden tocar
    BLOCKED_ABSOLUTE = [
        "/etc",
        "/usr",
        "/bin",
        "/sbin",
        "/boot",
        "/sys",
        "/proc",
        "/root",
        "/var",
    ]

    # Nombres de archivo que jamas se pueden tocar
    BLOCKED_FILENAMES = [
        ".env",
        ".ssh",
        ".gnupg",
        "id_rsa",
        "id_ed25519",
        "authorized_keys",
        "known_hosts",
        "passwd",
        "shadow",
        "sudoers",
    ]

    # Extensiones que jamas se pueden ejecutar directamente
    BLOCKED_EXEC_EXTENSIONS = [
        ".sh",   # usar tools/terminal en su lugar
        ".bash",
        ".zsh",
        ".fish",
    ]

    # ─────────────────────────────────────────
    #  CONFIGURABLE RULES — via .env
    # ─────────────────────────────────────────

    def __init__(self):
        # Raiz del proyecto — todo debe estar dentro
        self.project_root = Path(
            os.getenv("FORGE_PROJECT_ROOT", os.getcwd())
        ).resolve()

        # Extensiones de codigo que el agente puede ejecutar
        default_exts = ".py,.js,.ts,.go,.rs,.rb,.java"
        raw = os.getenv("FORGE_ALLOWED_EXTENSIONS", default_exts)
        self.allowed_extensions = [
            e.strip() for e in raw.split(",") if e.strip()
        ]

        # Maximo de bytes que puede escribir el agente en un solo archivo
        self.max_write_bytes = int(
            os.getenv("FORGE_MAX_WRITE_BYTES", str(1 * 1024 * 1024))  # 1MB
        )

        # Si el sandbox de ejecucion esta activo
        self.sandbox_enabled = (
            os.getenv("FORGE_SANDBOX", "true").lower() == "true"
        )

        # Timeout en segundos para ejecucion de codigo
        self.exec_timeout = int(os.getenv("FORGE_EXEC_TIMEOUT", "30"))

    def __repr__(self):
        return (
            f"SecurityConfig(\n"
            f"  project_root      = {self.project_root}\n"
            f"  allowed_extensions= {self.allowed_extensions}\n"
            f"  max_write_bytes   = {self.max_write_bytes}\n"
            f"  sandbox_enabled   = {self.sandbox_enabled}\n"
            f"  exec_timeout      = {self.exec_timeout}\n"
            f")"
        )