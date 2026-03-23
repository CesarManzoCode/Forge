from groq import Groq
from dotenv import load_dotenv
import os
import tiktoken
from llm.dev import dev_log_request, dev_log_response

load_dotenv()

# ─────────────────────────────────────────────
#  CONTEXT WINDOW CONFIG
#  llama-3.3-70b-versatile tiene 128k tokens.
#  Usamos cl100k como aproximacion — no hay
#  tokenizer oficial para llama pero es cercano.
# ─────────────────────────────────────────────

MODEL_CONTEXT_LIMIT = int(os.getenv("FORGE_CONTEXT_LIMIT", "128000"))
COMPRESS_AT         = float(os.getenv("FORGE_COMPRESS_AT", "0.80"))
COMPRESS_THRESHOLD  = int(MODEL_CONTEXT_LIMIT * COMPRESS_AT)

try:
    _ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:
    _ENCODER = None


def _count_tokens(messages: list[dict]) -> int:
    """
    Cuenta tokens del historial completo.
    Si tiktoken no esta disponible, estima por caracteres (1 token ≈ 4 chars).
    """
    if _ENCODER is None:
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // 4

    total = 0
    for msg in messages:
        # 4 tokens de overhead por mensaje (role, separadores)
        total += 4
        total += len(_ENCODER.encode(msg.get("content", "")))
    return total


class AI:
    def __init__(self, system_prompt: str = None):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model  = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.history: list[dict] = []
        self._system_prompt = system_prompt  # guardado para restaurar tras compresion

        if system_prompt:
            self.history.append({
                "role":    "system",
                "content": system_prompt,
            })

    # ─────────────────────────────────────────
    #  CHAT
    # ─────────────────────────────────────────

    def chat(self, message: str) -> str:
        self.history.append({
            "role":    "user",
            "content": message,
        })

        # Comprimir si se acerca al limite ANTES de enviar
        self._maybe_compress()

        start = dev_log_request(self.model, self.history)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
        )

        raw = response.choices[0].message.content
        dev_log_response(raw, start)

        self.history.append({
            "role":    "assistant",
            "content": raw,
        })

        return raw

    # ─────────────────────────────────────────
    #  CONTEXT WINDOW MANAGEMENT
    # ─────────────────────────────────────────

    def token_count(self) -> int:
        """Retorna el numero actual de tokens en el historial."""
        return _count_tokens(self.history)

    def _maybe_compress(self):
        """
        Si el historial supera COMPRESS_THRESHOLD, resume el historial
        intermedio y lo reemplaza con el resumen.

        Estructura del historial comprimido:
          [0] system prompt  (intacto)
          [1] user:      [HISTORY SUMMARY] resumen generado
          [2] assistant: Understood.
          [3..] mensajes recientes (ultimos N pares)
        """
        current_tokens = _count_tokens(self.history)
        if current_tokens < COMPRESS_THRESHOLD:
            return

        system = self._get_system()
        recent = self._get_recent_messages(keep_pairs=4)
        middle = self._get_middle_messages(keep_pairs=4)

        if not middle:
            return  # nada que comprimir todavia

        summary = self._summarize(middle)

        # Reconstruir historial comprimido
        new_history = []
        if system:
            new_history.append(system)
        new_history.append({
            "role":    "user",
            "content": f"[HISTORY SUMMARY]\n{summary}",
        })
        new_history.append({
            "role":    "assistant",
            "content": "Understood.",
        })
        new_history.extend(recent)

        self.history = new_history

        # Log en dev mode
        from llm.dev import DEV_MODE
        if DEV_MODE:
            compressed_tokens = _count_tokens(self.history)
            print(f"\n  ┌─[DEV:COMPRESSION]────────────────────────────────")
            print(f"  │  before : {current_tokens} tokens")
            print(f"  │  after  : {compressed_tokens} tokens")
            print(f"  │  saved  : {current_tokens - compressed_tokens} tokens")
            print(f"  └──────────────────────────────────────────────────\n")

    def _summarize(self, messages: list[dict]) -> str:
        """
        Llama al LLM para resumir un bloque de mensajes.
        Usa una llamada directa sin modificar self.history.
        """
        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:500]}"
            for m in messages
        )

        summary_prompt = (
            "Summarize the following conversation in 3-5 concise sentences. "
            "Focus on: decisions made, files created/modified, errors encountered, "
            "and current state. Be technical and specific.\n\n"
            f"{conversation_text}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a concise technical summarizer."},
                    {"role": "user",   "content": summary_prompt},
                ],
                max_tokens=300,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            # Si el resumen falla, retornar un placeholder para no romper el flujo
            return f"[Summary unavailable: {e}. Conversation compressed to save context.]"

    def _get_system(self) -> dict | None:
        if self.history and self.history[0]["role"] == "system":
            return self.history[0]
        return None

    def _get_recent_messages(self, keep_pairs: int) -> list[dict]:
        """
        Retorna los ultimos N pares user/assistant del historial.
        Excluye el system prompt.
        """
        non_system = [m for m in self.history if m["role"] != "system"]
        # Cada par = 2 mensajes
        keep = keep_pairs * 2
        return non_system[-keep:] if len(non_system) > keep else non_system

    def _get_middle_messages(self, keep_pairs: int) -> list[dict]:
        """
        Retorna los mensajes que NO son el system prompt
        ni los ultimos N pares — los candidatos a comprimir.
        """
        non_system = [m for m in self.history if m["role"] != "system"]
        keep = keep_pairs * 2
        if len(non_system) <= keep:
            return []
        return non_system[:-keep]

    # ─────────────────────────────────────────
    #  UTILS
    # ─────────────────────────────────────────

    def reset(self):
        """Limpia historial conservando el system prompt."""
        system = self._get_system()
        self.history = [system] if system else []

    def inject_context(self, content: str, label: str = "context"):
        """Inyecta informacion al historial como par user/assistant."""
        self.history.append({
            "role":    "user",
            "content": f"[{label}]\n{content}",
        })
        self.history.append({
            "role":    "assistant",
            "content": "Understood.",
        })

    def context_usage(self) -> dict:
        """
        Retorna el uso actual del context window.
        Util para mostrar en /status o dev mode.
        """
        current = _count_tokens(self.history)
        return {
            "tokens":    current,
            "limit":     MODEL_CONTEXT_LIMIT,
            "threshold": COMPRESS_THRESHOLD,
            "percent":   round(current / MODEL_CONTEXT_LIMIT * 100, 1),
            "will_compress_at": COMPRESS_THRESHOLD,
        }