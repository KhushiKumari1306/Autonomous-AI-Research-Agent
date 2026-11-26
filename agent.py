
import json
import time
import re
from google import genai

from config import GEMINI_API_KEY, MODEL_NAME, MAX_RETRIES
from planner import create_plan
from tools import web_search, calculator, save_report


# ============================================================
# INITIALIZATION
# ============================================================

client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# HELPER: LOG EVENTS
# ============================================================

def emit_log(message, event_type="info", event_callback=None):

    print(f"[{event_type.upper()}] {message}")

    if event_callback:
        try:
            event_callback(message, event_type)
        except Exception:
            pass


# ============================================================
# HELPER: LLM CALL WITH RETRIES
# ============================================================

def call_llm(prompt, max_attempts=3):

    """
    Calls Gemini with retry handling.

    Returns:
        Generated text if successful.
        None if all attempts fail.
    """

    for attempt in range(max_attempts):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

            if response.text:
                return response.text.strip()

            raise ValueError("LLM returned an empty response.")

        except Exception as e:

            print(
                f"[LLM ERROR] Attempt {attempt + 1}/"
                f"{max_attempts}: {e}"
            )

            if attempt < max_attempts - 1:

                wait_time = 2 * (attempt + 1)

                print(
                    f"[LLM RETRY] Waiting {wait_time} seconds..."
                )

                time.sleep(wait_time)

    return None


# ============================================================
# TOOL: LLM ANALYSIS
# ============================================================

def llm_analysis(task, context):

    """
    Analyze the collected information using the LLM.
    """

    prompt = f"""
You are the analysis component of an autonomous AI agent.

TASK:
{task}

INFORMATION COLLECTED:
{context}

INSTRUCTIONS:
1. Analyze the information carefully.
2. Identify important findings.
3. Answer the given task.
4. Mention uncertainty or missing information.
5. Do not invent facts.
6. Make your response clear and structured.
"""

    result = call_llm(prompt)

    if result is None:

        return (
            "LLM analysis could not be completed because "
            "the model service was temporarily unavailable.\n\n"
            "Available information:\n"
            f"{context}"
        )

    return result


# ============================================================
# TOOL: SELF-CORRECTION
# ============================================================

def recover_from_failure(
    task,
    tool,
    tool_input,
    error,
    event_callback=None
):

    """
    Ask the LLM to correct the input after a tool failure.

    If the LLM is unavailable, use a safe fallback.
    """

    emit_log(
        "Analyzing the tool failure...",
        "recovery",
        event_callback
    )

    prompt = f"""
You are the recovery component of an autonomous AI agent.

A tool execution has failed.

TASK:
{task}

TOOL:
{tool}

FAILED INPUT:
{tool_input}

ERROR:
{error}

Suggest a corrected input for the same tool.

Rules:
- For web_search, simplify or improve the search query.
- For calculator, correct the mathematical expression.
- Do not change the original task.
- Do not invent a result.
- Return ONLY valid JSON.

Format:
{{
    "corrected_input": "corrected input"
}}
"""

    response_text = call_llm(prompt, max_attempts=2)

    if response_text:

        try:

            # Remove possible Markdown code fences
            response_text = re.sub(
                r"```(?:json)?",
                "",
                response_text
            )

            response_text = response_text.replace(
                "```",
                ""
            ).strip()

            result = json.loads(response_text)

            corrected_input = result.get(
                "corrected_input"
            )

            if corrected_input:

                emit_log(
                    f"Corrected input: {corrected_input}",
                    "recovery",
                    event_callback
                )

                return corrected_input

        except Exception as e:

            emit_log(
                f"Could not parse recovery response: {e}",
                "warning",
                event_callback
            )

    # --------------------------------------------------------
    # FALLBACK RECOVERY
    # --------------------------------------------------------

    emit_log(
        "LLM recovery unavailable. Using safe fallback.",
        "warning",
        event_callback
    )

    if tool == "web_search":

        # Simplify the query
        corrected_input = str(tool_input)

        corrected_input = corrected_input.replace(
            "compare",
            "overview"
        )

        corrected_input = corrected_input.replace(
            "advantages disadvantages",
            "features and use cases"
        )

        return corrected_input

    # For calculator and other tools,
    # do not guess potentially incorrect inputs.
    return tool_input


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(tool, tool_input, observations, goal):

    """
    Execute the selected tool.
    """

    if tool == "web_search":

        return web_search(str(tool_input))


    elif tool == "calculator":

        return calculator(str(tool_input))


    elif tool == "llm_analysis":

        context = "\n\n".join(observations)

        return llm_analysis(
            task=str(tool_input),
            context=context
        )


    elif tool == "save_report":

        context = "\n\n".join(observations)

        report_prompt = f"""
Create a detailed Markdown report.

USER GOAL:
{goal}

INFORMATION COLLECTED:
{context}

The report should contain:

# Report

## Objective

## Research and Findings

## Analysis

## Tool Usage

## Errors and Recovery

## Limitations

## Conclusion

Use only the information collected.
Do not invent facts.
Clearly mention incomplete tasks.
"""

        report = llm_analysis(
            task=report_prompt,
            context=context
        )

        save_result = save_report(
            content=report,
            filename="agent_report.md"
        )

        return {
            "report": report,
            "save_status": save_result
        }


    else:

        raise ValueError(
            f"Unknown tool requested by planner: {tool}"
        )


# ============================================================
# FALLBACK PLAN
# ============================================================

def create_fallback_plan(goal):

    """
    Used only if the planner LLM is unavailable.

    This is a generic fallback plan, not a fixed final answer.
    """

    return {
        "goal": goal,
        "steps": [
            {
                "id": 1,
                "task": "Gather relevant information for the user goal.",
                "tool": "web_search",
                "input": goal
            },
            {
                "id": 2,
                "task": "Analyze the collected information.",
                "tool": "llm_analysis",
                "input": goal
            },
            {
                "id": 3,
                "task": "Create and save a structured report.",
                "tool": "save_report",
                "input": goal
            }
        ]
    }


# ============================================================
# MAIN AUTONOMOUS AGENT
# ============================================================

def run_agent(
    goal,
    inject_failure=False,
    event_callback=None
):

    """
    Main autonomous agent execution function.

    Workflow:
        1. Planning
        2. Tool execution
        3. Observation
        4. Error recovery
        5. Final report
    """

    logs = []
    observations = []

    failure_injected = False


    # --------------------------------------------------------
    # INTERNAL LOGGER
    # --------------------------------------------------------

    def log(message, event_type="info"):

        logs.append({
            "type": event_type,
            "message": str(message)
        })

        emit_log(
            message,
            event_type,
            event_callback
        )


    # --------------------------------------------------------
    # PHASE 1: PLANNING
    # --------------------------------------------------------

    log(
        "Creating an execution plan...",
        "planning"
    )

    try:

        # IMPORTANT: Planner is called only ONCE.
        plan = create_plan(goal)

        log(
            "Plan generated successfully.",
            "planning"
        )

    except Exception as e:

        log(
            f"Planner failed: {e}",
            "error"
        )

        log(
            "Using fallback plan.",
            "warning"
        )

        plan = create_fallback_plan(goal)


    # Validate plan
    if not isinstance(plan, dict):

        plan = create_fallback_plan(goal)


    if not isinstance(plan.get("steps"), list):

        plan = create_fallback_plan(goal)


    # Display plan
    log(
        json.dumps(plan, indent=2),
        "plan"
    )


    # --------------------------------------------------------
    # PHASE 2: EXECUTION
    # --------------------------------------------------------

    steps = plan.get("steps", [])

    total_steps = len(steps)

    log(
        f"Agent will execute {total_steps} steps.",
        "planning"
    )


    for index, step in enumerate(steps, start=1):

        step_id = step.get("id", index)

        task = step.get(
            "task",
            "No task description"
        )

        tool = step.get(
            "tool",
            ""
        )

        tool_input = step.get(
            "input",
            ""
        )


        log(
            f"Executing step {step_id}/{total_steps}: {task}",
            "step"
        )

        log(
            f"Selected tool: {tool}",
            "tool"
        )


        success = False

        result = None

        current_input = tool_input


        # ----------------------------------------------------
        # RETRY LOOP
        # ----------------------------------------------------

        for attempt in range(MAX_RETRIES + 1):

            try:

                # ----------------------------------------------
                # DELIBERATE FAILURE TEST
                # ----------------------------------------------

                if (
                    inject_failure
                    and not failure_injected
                    and tool == "web_search"
                ):

                    failure_injected = True

                    raise TimeoutError(
                        "Simulated web search timeout "
                        "for self-correction testing."
                    )


                # ----------------------------------------------
                # EXECUTE TOOL
                # ----------------------------------------------

                result = execute_tool(
                    tool=tool,
                    tool_input=current_input,
                    observations=observations,
                    goal=goal
                )


                success = True


                log(
                    f"Step {step_id} completed successfully.",
                    "success"
                )


                log(
                    f"Observation: {str(result)[:1500]}",
                    "observation"
                )


                break


            # ----------------------------------------------
            # ERROR HANDLING
            # ----------------------------------------------

            except Exception as e:

                error_message = str(e)


                log(
                    f"Attempt {attempt + 1} failed: "
                    f"{error_message}",
                    "error"
                )


                # Retry if attempts remain
                if attempt < MAX_RETRIES:


                    log(
                        "Attempting self-correction...",
                        "recovery"
                    )


                    current_input = recover_from_failure(
                        task=task,
                        tool=tool,
                        tool_input=current_input,
                        error=error_message,
                        event_callback=event_callback
                    )


                    log(
                        f"Retrying tool: {tool}",
                        "recovery"
                    )


                    # Small delay between retries
                    time.sleep(1)


                else:

                    log(
                        f"Step {step_id} failed after "
                        f"{MAX_RETRIES + 1} attempts.",
                        "error"
                    )


        # ----------------------------------------------------
        # STORE OBSERVATIONS
        # ----------------------------------------------------

        if success:

            observations.append(
                f"""
STEP {step_id}

TASK:
{task}

TOOL:
{tool}

INPUT:
{current_input}

RESULT:
{result}
"""
            )

        else:

            observations.append(
                f"""
STEP {step_id}

TASK:
{task}

TOOL:
{tool}

STATUS:
FAILED

ERROR:
The tool could not complete this step after retries.
"""
            )


    # --------------------------------------------------------
    # PHASE 3: FINAL REPORT
    # --------------------------------------------------------

    log(
        "Generating final summary...",
        "final"
    )


    final_context = "\n\n".join(observations)


    final_prompt = f"""
You are the final reporting component of an autonomous AI agent.

USER GOAL:
{goal}

EXECUTION PLAN:
{json.dumps(plan, indent=2)}

EXECUTION OBSERVATIONS:
{final_context}

Create a structured final report in Markdown.

Include:

# Final Report

## Objective

## Actions Performed

## Findings

## Tool Usage

## Errors and Recovery

## Incomplete Tasks

## Conclusion

Important:
- Be truthful about what the agent completed.
- Do not claim failed tasks were successful.
- Do not invent results.
- Mention unavailable information.
"""


    final_result = call_llm(
        final_prompt,
        max_attempts=3
    )


    # Fallback if final LLM call fails
    if final_result is None:

        log(
            "Final LLM report unavailable. "
            "Generating fallback summary.",
            "warning"
        )


        final_result = f"""
# Agent Execution Report

## Objective

{goal}

## Execution Plan

{json.dumps(plan, indent=2)}

## Observations

{final_context}

## Conclusion

The agent completed its execution loop.

Some analysis or reporting functionality may have been
limited because the LLM service was temporarily unavailable.
"""


    log(
        "Agent execution completed.",
        "success"
    )


    # --------------------------------------------------------
    # RETURN STRUCTURED RESULT
    # --------------------------------------------------------

    return {

        "goal": goal,

        "plan": plan,

        "observations": observations,

        "logs": logs,

        "final_result": final_result

    }
