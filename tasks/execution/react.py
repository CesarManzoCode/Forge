"""
tasks/execution/react.py — Loop ReAct por subtask.

Por cada subtask, el LLM itera:
  THINK  → razona que necesita hacer
  ACT    → propone una tool con sus args
  OBSERVE→ el engine ejecuta y devuelve el resultado
  ...repite hasta declarar la subtask done o encontrar un error

El LLM siempre responde JSON. Dos formatos posibles:

  Paso intermedio:
  {
    "thought": "I need to read the file to understand the current structure",
    "tool":    "read_file",
    "args":    {"path": "src/auth.py"}
  }

  Subtask completada:
  {
    "thought": "The file has been written and tests pass",
    "done":    true,
    "result":  "Created src/auth.py with JWT authentication logic"
  }
"""

import json
from dataclasses import dataclass, field
from llm.ai import AI
from llm.prompts import Executor
from tasks.execution.registry import registry
from src.security import SecurityError


MAX_STEPS = int(__import__("os").getenv("FORGE_MAX_STEPS", "20"))


# ─────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class Step:
    """Un paso dentro del loop ReAct."""
    thought:     str
    tool:        str | None = None
    args:        dict = field(default_factory=dict)
    observation: str | None = None   # resultado de ejecutar la tool
    error:       str | None = None   # si la tool fallo


@dataclass
class ReactResult:
    """Resultado final de ejecutar una subtask completa."""
    success:     bool
    result:      str          # resumen si success, motivo si fallo
    steps:       list[Step]   # historial completo para debug y contexto
    steps_taken: int


# ─────────────────────────────────────────────
#  REACT LOOP
# ─────────────────────────────────────────────

class ReactLoop:

    def __init__(self, ai: AI):
        self.ai = ai

    def run(self, subtask: dict, project_context: str, task_context: str) -> ReactResult:
        steps: list[Step] = []

        initial_prompt = Executor.run_subtask(
            subtask=subtask,
            project_context=project_context,
            task_context=task_context,
        )

        raw = self.ai.chat(initial_prompt)

        for step_num in range(MAX_STEPS):
            parsed, parse_error = self._parse_response(raw)

            if parse_error:
                raw = self.ai.chat(
                    f"Invalid JSON: {parse_error}. "
                    f"Respond ONLY with a JSON object."
                )
                parsed, parse_error = self._parse_response(raw)
                if parse_error:
                    return ReactResult(
                        success=False,
                        result=f"Agent produced invalid JSON twice: {parse_error}",
                        steps=steps,
                        steps_taken=step_num + 1,
                    )

            thought   = parsed.get("thought", "")

            if parsed.get("done"):
                steps.append(Step(thought=thought))
                return ReactResult(
                    success=True,
                    result=parsed.get("result", "Subtask completed."),
                    steps=steps,
                    steps_taken=step_num + 1,
                )

            tool_name = parsed.get("tool")
            tool_args = parsed.get("args", {})

            if not tool_name:
                raw = self.ai.chat(
                    "Propose a tool or declare done. "
                    "JSON: {\"tool\": \"...\", \"args\": {...}} "
                    "or {\"done\": true, \"result\": \"...\"}"
                )
                continue

            observation, error = self._execute_tool(tool_name, tool_args)

            step = Step(
                thought=thought,
                tool=tool_name,
                args=tool_args,
                observation=observation,
                error=error,
            )
            steps.append(step)

            if error:
                return ReactResult(
                    success=False,
                    result=self._format_failure(subtask, step),
                    steps=steps,
                    steps_taken=step_num + 1,
                )

            # Observation corta — sin repetir formato JSON despues del primer paso
            raw = self.ai.chat(self._observation_prompt(tool_name, observation, step_num))

        return ReactResult(
            success=False,
            result=(
                f"Subtask '{subtask['description']}' reached the step limit "
                f"({MAX_STEPS} steps). Consider breaking it into smaller subtasks."
            ),
            steps=steps,
            steps_taken=MAX_STEPS,
        )

    # ─────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────

    def _parse_response(self, raw: str) -> tuple[dict, str | None]:
        """
        Parsea la respuesta del LLM como JSON.
        Retorna (parsed_dict, error_string).
        Si no hay error, error_string es None.
        """
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return {}, "No JSON object found in response."
            return json.loads(raw[start:end]), None
        except json.JSONDecodeError as e:
            return {}, str(e)

    def _execute_tool(self, tool_name: str, args: dict) -> tuple[str | None, str | None]:
        """
        Ejecuta una tool via registry.
        Retorna (observation, error) — uno de los dos siempre es None.
        """
        try:
            result = registry.call(tool_name, args)
            return result, None
        except KeyError as e:
            return None, f"Tool not found: {e}"
        except TypeError as e:
            return None, f"Wrong arguments for '{tool_name}': {e}"
        except SecurityError as e:
            return None, f"Security block: {e}"
        except (RuntimeError, FileNotFoundError, ValueError, PermissionError) as e:
            return None, str(e)
        except Exception as e:
            return None, f"Unexpected error in '{tool_name}': {type(e).__name__}: {e}"

    def _observation_prompt(self, tool_name: str, observation: str, step_num: int) -> str:
        """
        Primer paso: incluye recordatorio del formato.
        Pasos siguientes: solo el resultado — el LLM ya sabe el formato.
        """
        # Truncar observaciones muy largas para no inflar el historial
        max_obs = 2000
        if len(observation) > max_obs:
            observation = observation[:max_obs] + f"\n[...truncated at {max_obs} chars]"

        if step_num == 0:
            return (
                f"[{tool_name}] {observation}\n\n"
                f"Next step JSON: {{\"thought\":\"...\",\"tool\":\"...\",\"args\":{{...}}}} "
                f"or {{\"thought\":\"...\",\"done\":true,\"result\":\"...\"}}"
            )
        # Pasos siguientes — solo el resultado
        return f"[{tool_name}] {observation}"

    def _format_failure(self, subtask: dict, step: Step) -> str:
        """Formatea el reporte de fallo para el usuario."""
        return (
            f"Subtask {subtask['id']} failed: '{subtask['description']}'\n\n"
            f"Step that failed:\n"
            f"  Thought    : {step.thought}\n"
            f"  Tool       : {step.tool}\n"
            f"  Args       : {json.dumps(step.args, ensure_ascii=False)}\n"
            f"  Error      : {step.error}"
        )