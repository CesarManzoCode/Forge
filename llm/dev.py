"""
dev.py — DEVELOPER_MODE para Forge.

Activar en .env:
    DEV_MODE=true

Uso en ai.py:
    from llm.dev import dev_log_request, dev_log_response
"""

import os
import json
import time

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

WIDTH = 64
DEV_WIDTH = 60


# ─────────────────────────────────────────────
#  DISPLAY HELPERS
# ─────────────────────────────────────────────

def _header(label: str):
    pad = DEV_WIDTH - len(label) - 4
    print(f"\n  ┌─[DEV:{label}]" + "─" * max(0, pad))

def _footer():
    print(f"  └" + "─" * (DEV_WIDTH - 1))

def _line(text: str = ""):
    if text:
        # Word-wrap at DEV_WIDTH - 6 to account for the prefix
        max_len = DEV_WIDTH - 6
        while len(text) > max_len:
            print(f"  │  {text[:max_len]}")
            text = text[max_len:]
    print(f"  │  {text}")


def _print_block(label: str, lines: list[str]):
    _header(label)
    for l in lines:
        _line(l)
    _footer()


# ─────────────────────────────────────────────
#  REQUEST LOG
#  Llamar antes de enviar a la API
# ─────────────────────────────────────────────

def dev_log_request(model: str, messages: list[dict]) -> float:
    """Logs the full API request. Returns start timestamp for timing."""
    if not DEV_MODE:
        return time.time()

    lines = []
    lines.append(f"model    : {model}")
    lines.append(f"messages : {len(messages)}")
    lines.append("")

    for i, msg in enumerate(messages):
        role = msg.get("role", "?").upper()
        content = msg.get("content", "")

        # Truncate very long messages but show structure
        if len(content) > 300:
            preview = content[:300].replace("\n", "↵ ")
            lines.append(f"[{i}] {role} ({len(content)} chars)")
            lines.append(f"    {preview}...")
        else:
            content_preview = content.replace("\n", "↵ ")
            lines.append(f"[{i}] {role}")
            lines.append(f"    {content_preview}")

        lines.append("")

    _print_block("REQUEST", lines)
    return time.time()


# ─────────────────────────────────────────────
#  RESPONSE LOG
#  Llamar despues de recibir la respuesta
# ─────────────────────────────────────────────

def dev_log_response(raw_response: str, start_time: float):
    """Logs the raw LLM response and elapsed time."""
    if not DEV_MODE:
        return

    elapsed = time.time() - start_time
    lines = []
    lines.append(f"time     : {elapsed:.2f}s")
    lines.append(f"length   : {len(raw_response)} chars")
    lines.append("")

    # Check if response contains JSON and pretty print it
    json_start = raw_response.find("{")
    json_end = raw_response.rfind("}") + 1

    if json_start != -1 and json_end > json_start:
        # Text before JSON
        before = raw_response[:json_start].strip()
        if before:
            lines.append("── text before json")
            for l in before.split("\n"):
                lines.append(f"  {l}")
            lines.append("")

        # Pretty print the JSON
        try:
            parsed = json.loads(raw_response[json_start:json_end])
            pretty = json.dumps(parsed, indent=2)
            lines.append("── json payload")
            for l in pretty.split("\n"):
                lines.append(f"  {l}")
        except json.JSONDecodeError:
            lines.append("── raw (invalid json detected)")
            for l in raw_response.split("\n"):
                lines.append(f"  {l}")

        # Text after JSON
        after = raw_response[json_end:].strip()
        if after:
            lines.append("")
            lines.append("── text after json")
            for l in after.split("\n"):
                lines.append(f"  {l}")
    else:
        # Plain text response, no JSON
        lines.append("── raw response")
        for l in raw_response.split("\n"):
            lines.append(f"  {l}")

    _print_block("RESPONSE", lines)