"""
prompts.py — Todos los prompts de Forge en un solo lugar.

Uso:
    from llm.prompts import SYSTEM, Planner, Chat

Cada clase agrupa prompts del mismo dominio.
Los prompts que necesitan datos usan .format() o f-strings via metodos.
"""


# ─────────────────────────────────────────────
#  SYSTEM PROMPT
#  El primero en el historial. Define quien es Forge.
# ─────────────────────────────────────────────

SYSTEM = """You are Forge, an expert AI agent built to assist software developers.

Your core traits:
- Precise and technical. No filler, no padding.
- You reason step by step before acting.
- You never assume — if something is unclear, you ask once, concisely.
- You never execute anything without explicit user confirmation.
- When planning, you think about what could go wrong before committing to a step.

Your current capabilities:
- Read and write files
- Execute code and terminal commands
- Search the internet
- Plan and execute complex development tasks as ordered subtasks

Always stay in your role as Forge. Never break character."""


# ─────────────────────────────────────────────
#  PLANNER PROMPTS
#  Usados en /task para generar y revisar planes
# ─────────────────────────────────────────────

class Planner:

    @staticmethod
    def generate(task_description: str) -> str:
        return f"""You are acting as a senior software engineer and task planner.

Your job is to analyze the following task and break it down into small, 
chronological, and executable subtasks for an AI agent.

Rules for planning:
- Each subtask must be concrete and achievable on its own
- No subtask should be vague (bad: "set up the project", good: "create pyproject.toml with these dependencies: ...")
- If a subtask depends on a previous one, declare it in depends_on
- Do not include subtasks that require human decisions mid-execution
- Maximum 10 subtasks. If the task needs more, it should be split into multiple tasks
- Be conservative — only include what is strictly necessary

Respond ONLY with a valid JSON object. No explanation, no markdown, no extra text.
Exact format required:

{{
  "title": "short title, max 6 words",
  "description": "original task restated clearly",
  "estimated_subtasks": <number>,
  "risk_level": "low | medium | high",
  "subtasks": [
    {{
      "id": 1,
      "description": "concrete action to take",
      "status": "pending",
      "depends_on": [],
      "result": null,
      "context_written": []
    }}
  ]
}}

Task to plan:
{task_description}"""

    @staticmethod
    def clarify(task_description: str, question: str) -> str:
        return f"""You are planning the following task:

{task_description}

Before generating the full plan, you identified this blocker:
{question}

Ask the user this question clearly and concisely. One question only.
Do not generate the plan yet."""

    @staticmethod
    def replan(original_plan: str, feedback: str) -> str:
        return f"""You previously generated this task plan:

{original_plan}

The user reviewed it and provided this feedback:
{feedback}

Revise the plan accordingly. Apply only the requested changes.
Respond ONLY with the complete updated JSON object in the same format as before.
No explanation, no markdown."""


# ─────────────────────────────────────────────
#  EXECUTOR PROMPTS
#  Usados cuando execution/ corre cada subtask
# ─────────────────────────────────────────────

class Executor:

    @staticmethod
    def run_subtask(subtask: dict, project_context: str, task_context: str) -> str:
        return f"""You are executing a specific subtask as part of a larger development task.

Project context:
{project_context}

Current task context:
{task_context}

Subtask to execute (id: {subtask['id']}):
{subtask['description']}

Instructions:
- Focus only on this subtask. Do not jump ahead.
- Use the available tools to complete it.
- When done, report the result concisely.
- If you encounter a blocker, report it immediately — do not improvise around it.
- Do not modify files outside the scope of this subtask."""

    @staticmethod
    def report_done(subtask_id: int, result: str) -> str:
        return f"""Subtask {subtask_id} is complete.

Result:
{result}

Summarize what was done in one or two sentences for the task log.
Be factual, no commentary."""

    @staticmethod
    def report_blocked(subtask_id: int, reason: str) -> str:
        return f"""Subtask {subtask_id} is blocked.

Reason:
{reason}

Explain the blocker clearly so the user can decide how to proceed.
Do not suggest solutions unless explicitly asked."""


# ─────────────────────────────────────────────
#  CONTEXT PROMPTS
#  Para inyectar informacion al historial del LLM
# ─────────────────────────────────────────────

class Context:

    @staticmethod
    def inject_project(project_info: str) -> str:
        return f"""[PROJECT CONTEXT]
The following is persistent information about the current project.
Use it to inform all your decisions.

{project_info}

Acknowledge with: understood."""

    @staticmethod
    def inject_task(task_info: str) -> str:
        return f"""[TASK CONTEXT]
The following is the current state of the active task.
This updates as subtasks are completed.

{task_info}

Acknowledge with: understood."""

    @staticmethod
    def inject_memory(user_preferences: str) -> str:
        return f"""[USER PREFERENCES]
The following are known preferences and patterns from this user.
Apply them silently — do not mention them unless relevant.

{user_preferences}

Acknowledge with: understood."""


# ─────────────────────────────────────────────
#  CHAT PROMPTS
#  Para conversacion general fuera de tasks
# ─────────────────────────────────────────────

class Chat:

    @staticmethod
    def clarify_input(user_message: str) -> str:
        return f"""The user sent this message which is ambiguous:

"{user_message}"

Ask one clarifying question to understand their intent.
Be direct and concise."""

    CANNOT_EXECUTE = """I can plan this task but I won't execute anything until you type /start.
Review the plan above and let me know if you want changes before we begin."""

    TASK_ALREADY_RUNNING = """There is already a task in execution. 
Type /status to see the current progress, or /reset to start fresh."""

    NO_TASK_TO_START = """No task has been planned yet.
Use /task to describe what you want to accomplish."""

    PLAN_READY = """Plan is ready. Review the subtasks above.

  /start     — execute the plan as shown
  /task      — describe a new task (discards current plan)
  /exit      — quit

No action will be taken until you type /start."""