"""
challenges.py â€” curated "build this from a goal" curricula.

Each challenge maps a plain-English goal (matched by keyword) to an ordered
list of steps. Each step is {"explanation": <English instruction>,
"code": <the line of code that satisfies it>}. The frontend shows only the
explanation, the learner writes code next to it, and /api/check (already
built for the Practice tab) grades it against `code`.

WHY CURATED, NOT GENERATED
Turning an arbitrary goal ("build me a chess engine") into a good teaching
curriculum is a genuinely open-ended language task â€” the kind an LLM is
suited for, not a regex engine. This file is the honest, working version
of that idea: a small, real library instead of a fake "generates anything"
promise. See README "extend first" #1 for how to plug an LLM in here so
GOAL_CHALLENGES can grow to cover any goal, with these entries kept as
free, instant, offline fallbacks for the common ones.
"""

from typing import Dict, List

CHALLENGES: Dict[str, dict] = {
    "calculator": {
        "title": "A simple calculator",
        "keywords": ["calculator", "calculate", "arithmetic", "add subtract multiply divide"],
        "steps": [
            {"explanation": "Define a function named `calculate` that takes in three things: the first number, the second number, and the operator symbol (like '+' or '-').",
             "code": "def calculate(a, b, operator):"},
            {"explanation": "Check if the operator is a plus sign.",
             "code": "    if operator == '+':"},
            {"explanation": "Send back the sum of the two numbers.",
             "code": "        return a + b"},
            {"explanation": "Otherwise, check if the operator is a minus sign.",
             "code": "    elif operator == '-':"},
            {"explanation": "Send back the first number minus the second.",
             "code": "        return a - b"},
            {"explanation": "Otherwise, check if the operator is a multiplication sign (an asterisk).",
             "code": "    elif operator == '*':"},
            {"explanation": "Send back the product of the two numbers.",
             "code": "        return a * b"},
            {"explanation": "Otherwise, check if the operator is a division sign (a forward slash).",
             "code": "    elif operator == '/':"},
            {"explanation": "Guard against dividing by zero: check that the second number isn't zero.",
             "code": "        if b != 0:"},
            {"explanation": "Send back the first number divided by the second.",
             "code": "            return a / b"},
            {"explanation": "Otherwise (that would be dividing by zero), send back `None` to signal it can't be done.",
             "code": "        return None"},
            {"explanation": "Otherwise (none of the known operators matched), send back `None` to signal an invalid operator.",
             "code": "    return None"},
        ],
    },
    "todo": {
        "title": "A simple to-do list",
        "keywords": ["todo", "to-do", "task list", "task manager"],
        "steps": [
            {"explanation": "Start with an empty list called `tasks` to hold everything on the to-do list.",
             "code": "tasks = []"},
            {"explanation": "Define a function named `add_task` that takes in one thing: the task text.",
             "code": "def add_task(task):"},
            {"explanation": "Add the task onto the end of the `tasks` list.",
             "code": "    tasks.append(task)"},
            {"explanation": "Define a function named `remove_task` that takes in the task text to remove.",
             "code": "def remove_task(task):"},
            {"explanation": "Check that the task is actually in the list before trying to remove it.",
             "code": "    if task in tasks:"},
            {"explanation": "Remove that task from the list.",
             "code": "        tasks.remove(task)"},
            {"explanation": "Define a function named `list_tasks` that takes in nothing.",
             "code": "def list_tasks():"},
            {"explanation": "Loop through the tasks list, one item at a time, calling each one `task`.",
             "code": "    for task in tasks:"},
            {"explanation": "Print the task so it shows up in the console.",
             "code": "        print(task)"},
        ],
    },
}


def find_challenge(goal: str) -> List[str]:
    """Return challenge ids whose keywords appear in the goal text, best match first."""
    goal_lower = goal.lower()
    scored = []
    for cid, challenge in CHALLENGES.items():
        hits = sum(1 for kw in challenge["keywords"] if kw in goal_lower)
        if hits:
            scored.append((hits, cid))
    scored.sort(reverse=True)
    return [cid for _, cid in scored]
