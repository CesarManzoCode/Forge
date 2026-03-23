from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()


class AI:
    def __init__(self, system_prompt: str = None):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.history: list[dict] = []

        if system_prompt:
            self.history.append({
                "role": "system",
                "content": system_prompt
            })

    def chat(self, message: str) -> str:
        self.history.append({
            "role": "user",
            "content": message
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
        )

        reply = response.choices[0].message.content

        self.history.append({
            "role": "assistant",
            "content": reply
        })

        return reply

    def reset(self):
        system = self.history[0] if self.history and self.history[0]["role"] == "system" else None
        self.history = [system] if system else []

    def inject_context(self, content: str, label: str = "context"):
        """Inyecta informacion al historial sin que cuente como turno del usuario."""
        self.history.append({
            "role": "user",
            "content": f"[{label}]\n{content}"
        })
        self.history.append({
            "role": "assistant",
            "content": "Entendido."
        })