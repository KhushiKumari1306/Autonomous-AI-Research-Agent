import json
import re

from google import genai
from config import GEMINI_API_KEY, MODEL_NAME


client = genai.Client(api_key=GEMINI_API_KEY)


def create_plan(goal: str) -> dict:

    prompt = f"""
You are an intelligent planning engine for an autonomous AI agent.

Your task is to create a practical plan for achieving the user's goal.

USER GOAL:
{goal}

AVAILABLE TOOLS:
1. web_search
   - Search the live internet.
   - Input must be a search query.

2. calculator
   - Perform mathematical calculations.
   - Input must be a mathematical expression.

3. llm_analysis
   - Analyze, summarize, compare, and reason over
     information collected by the agent.
   - Input should describe the analysis task.

4. save_report
   - Save the final report as a Markdown file.
   - Input should describe the report to create.

RULES:
- Break the goal into logical steps.
- Make the steps specific and actionable.
- Use tools whenever external data or calculations are needed.
- Do not invent facts.
- Do not use unnecessary steps.
- Create between 2 and 6 steps.
- The plan must be adaptable if a tool fails.
- Use llm_analysis for reasoning over collected information.
- Use save_report when a report/document is requested.

Return ONLY valid JSON in this format:

{{
    "goal": "User goal",
    "steps": [
        {{
            "id": 1,
            "task": "Description of the step",
            "tool": "web_search",
            "input": "Search query"
        }}
    ]
}}
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    text = response.text.strip()

    # Remove code fences if the model adds them
    text = re.sub(
        r"```(?:json)?",
        "",
        text
    ).replace("```", "").strip()

    try:
        plan = json.loads(text)

    except json.JSONDecodeError as e:
        raise ValueError(
            f"Planner returned invalid JSON: {e}\n{text}"
        )

    # Basic validation
    if "steps" not in plan:
        raise ValueError("Plan does not contain steps.")

    if not isinstance(plan["steps"], list):
        raise ValueError("Steps must be a list.")

    return plan 