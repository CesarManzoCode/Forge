"""
tasks/execution/react.py — Loop ReAct por subtask.
"""

import json
from dataclasses import dataclass, field
from llm.ai import AI
from llm.prompts import Executor as ExecutorPrompts
from tasks.execution.registry import registry
from src.security import SecurityError
from logs.logger import logger

MAX_STEPS = int(__import__("os").getenv("FORGE_MAX_STEPS", "20"))


@dataclass
class Step:
    thought:     str
    tool:        str | None       = None
    args:        dict             = field(default_factory=dict)
    observation: str | None       = None
    error:       str | None       = None


@dataclass
class ReactResult:
    success:     bool
    result:      str
    steps:       list[Step]
    steps_taken: int


class ReactLoop:

    def __init__(self, ai: AI):
        self.ai = ai

    def run(self, subtask: dict, project_context: str, task_context: str) -> ReactResult:
        steps: list[Step] = []

        initial_prompt = ExecutorPrompts.run_subtask(
            subtask=subtask,
            project_context=project_context,
            task_context=task_context,
        )

        raw = self.ai.chat(initial_prompt)

        for step_num in range(MAX_STEPS):
            parsed, parse_error = self._parse_response(raw)

            if parse_error:
                raw = self.ai.chat(
                    f"Invalid JSON: {parse_error}. Respond ONLY with a JSON object."
                )
                parsed, parse_error = self._parse_response(raw)
                if parse_error:
                    return ReactResult(
                        success=False,
                        result=f"Agent produced invalid JSON twice: {parse_error}",
                        steps=steps,
                        steps_taken=step_num + 1,
                    )

            thought = parsed.get("thought", "")

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
                    'Propose a tool or declare done. '
                    'JSON: {"tool": "...", "args": {...}} '
                    'or {"done": true, "result": "..."}'
                )
                continue

            observation, error = self._execute_tool(
                tool_name, tool_args, subtask.get("id")
            )

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

    def _parse_response(self, raw: str) -> tuple[dict, str | None]:
        try:
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return {}, "No JSON object found in response."
            return json.loads(raw[start:end]), None
        except json.JSONDecodeError as e:
            return {}, str(e)

    def _execute_tool(self, tool_name: str, args: dict, subtask_id: int = None) -> tuple[str | None, str | None]:
        try:
            result = registry.call(tool_name, args)
            logger.agent_action(tool_name, args, result, subtask_id)
            return result, None
        except KeyError as e:
            err = f"Tool not found: {e}"
        except TypeError as e:
            err = f"Wrong arguments for '{tool_name}': {e}"
        except SecurityError as e:
            err = f"Security block: {e}"
        except (RuntimeError, FileNotFoundError, ValueError, PermissionError) as e:
            err = str(e)
        except Exception as e:
            err = f"Unexpected error in '{tool_name}': {type(e).__name__}: {e}"

        logger.agent_error(tool_name, args, err, subtask_id)
        return None, err

    def _observation_prompt(self, tool_name: str, observation: str, step_num: int) -> str:
        max_obs = 2000
        if len(observation) > max_obs:
            observation = observation[:max_obs] + f"\n[...truncated at {max_obs} chars]"

        if step_num == 0:
            return (
                f"[{tool_name}] {observation}\n\n"
                'Next: {"thought":"...","tool":"...","args":{...}} '
                'or {"thought":"...","done":true,"result":"..."}'
            )
        return f"[{tool_name}] {observation}"

    def _format_failure(self, subtask: dict, step: Step) -> str:
        return (
            f"Subtask {subtask['id']} failed: '{subtask['description']}'\n\n"
            f"  Thought : {step.thought}\n"
            f"  Tool    : {step.tool}\n"
            f"  Args    : {json.dumps(step.args, ensure_ascii=False)}\n"
            f"  Error   : {step.error}"
        )