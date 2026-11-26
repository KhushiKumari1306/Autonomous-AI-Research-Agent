
import json
import streamlit as st

from agent import run_agent


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Autonomous AI Research Agent",
    page_icon="🤖",
    layout="wide"
)


# ============================================================
# SESSION STATE
# ============================================================

if "agent_result" not in st.session_state:
    st.session_state.agent_result = None

if "execution_logs" not in st.session_state:
    st.session_state.execution_logs = []


# ============================================================
# HEADER
# ============================================================

st.title("🤖 Autonomous AI Research Agent")

st.markdown(
    """
    ### Goal-driven AI agent

    Enter a high-level goal. The agent will:

    - 🧠 Generate a plan using an LLM
    - 🔧 Select and execute tools
    - 🔍 Observe tool outputs
    - 🔄 Recover from failures
    - 📄 Generate a structured final report
    """
)

st.divider()


# ============================================================
# USER INPUT
# ============================================================

st.subheader("🎯 Define Your Goal")

goal = st.text_area(
    label="What should the AI agent accomplish?",
    placeholder=(
        "Example: Research three popular AI agent frameworks, "
        "compare their features, advantages, disadvantages, "
        "and use cases. Calculate 18% of 120 and create "
        "a Markdown report."
    ),
    height=150,
    key="goal_input"
)


# ============================================================
# OPTIONS
# ============================================================

col1, col2 = st.columns(2)

with col1:

    inject_failure = st.checkbox(
        "🧪 Enable deliberate failure test",
        help=(
            "Inject a simulated web-search failure to "
            "demonstrate the agent's recovery mechanism."
        )
    )


with col2:

    st.info(
        "The agent uses Gemini for reasoning and Tavily "
        "for live web research."
    )


# ============================================================
# RUN BUTTON
# ============================================================

run_button = st.button(
    "🚀 Run Autonomous Agent",
    type="primary",
    use_container_width=True
)


# ============================================================
# LIVE EXECUTION LOG AREA
# ============================================================

live_log_placeholder = st.empty()


# ============================================================
# CALLBACK FOR LIVE LOGGING
# ============================================================

def display_event(message, event_type):

    """
    Called by agent.py whenever an execution event occurs.
    Updates the live log display.
    """

    st.session_state.execution_logs.append(
        {
            "type": event_type,
            "message": str(message)
        }
    )

    formatted_logs = []

    for log_entry in st.session_state.execution_logs:

        log_type = log_entry["type"].upper()

        log_message = log_entry["message"]

        formatted_logs.append(
            f"[{log_type}] {log_message}"
        )


    live_log_placeholder.code(
        "\n\n".join(formatted_logs),
        language="text"
    )


# ============================================================
# EXECUTE AGENT
# ============================================================

if run_button:

    if not goal.strip():

        st.warning(
            "⚠️ Please enter a goal before running the agent."
        )

    else:

        # Clear previous results
        st.session_state.agent_result = None

        st.session_state.execution_logs = []

        live_log_placeholder.empty()


        # Execution status
        status_container = st.status(
            "🤖 Agent is starting...",
            expanded=True
        )


        try:

            with st.spinner(
                "Agent is planning, reasoning, and executing tools..."
            ):

                result = run_agent(
                    goal=goal.strip(),
                    inject_failure=inject_failure,
                    event_callback=display_event
                )


            # Save result in session state
            st.session_state.agent_result = result


            status_container.update(
                label="✅ Agent execution completed",
                state="complete",
                expanded=False
            )


            st.success(
                "The agent finished its execution."
            )


        except Exception as e:

            status_container.update(
                label="❌ Agent execution failed",
                state="error",
                expanded=True
            )


            st.error(
                f"An unexpected error occurred: {str(e)}"
            )


# ============================================================
# DISPLAY RESULTS
# ============================================================

result = st.session_state.agent_result


if result is not None:

    st.divider()


    # ========================================================
    # EXECUTION SUMMARY
    # ========================================================

    st.header("📊 Execution Summary")


    plan = result.get("plan", {})

    steps = plan.get("steps", [])

    observations = result.get(
        "observations",
        []
    )

    logs = result.get(
        "logs",
        []
    )


    total_steps = len(steps)

    successful_steps = sum(
        1
        for observation in observations
        if "STATUS:\nFAILED" not in observation
    )


    failed_steps = total_steps - successful_steps


    metric1, metric2, metric3 = st.columns(3)


    with metric1:

        st.metric(
            "Total Planned Steps",
            total_steps
        )


    with metric2:

        st.metric(
            "Successful Steps",
            successful_steps
        )


    with metric3:

        st.metric(
            "Failed Steps",
            failed_steps
        )


    # ========================================================
    # PLAN
    # ========================================================

    st.header("🧠 Agent Planning")


    st.markdown(
        "**Original Goal:**"
    )

    st.write(
        result.get("goal", "")
    )


    with st.expander(
        "View complete generated plan",
        expanded=True
    ):

        for index, step in enumerate(steps, start=1):

            step_id = step.get(
                "id",
                index
            )

            task = step.get(
                "task",
                "Task description unavailable"
            )

            tool = step.get(
                "tool",
                "Unknown tool"
            )

            tool_input = step.get(
                "input",
                ""
            )


            st.markdown(
                f"### Step {step_id}: {task}"
            )


            col_a, col_b = st.columns(2)


            with col_a:

                st.markdown(
                    f"**Selected Tool:** `{tool}`"
                )


            with col_b:

                st.markdown(
                    "**Input:**"
                )

                st.code(
                    str(tool_input),
                    language="text"
                )


            st.divider()


    # ========================================================
    # OBSERVATIONS
    # ========================================================

    st.header("🔍 Execution Observations")


    if observations:

        for index, observation in enumerate(
            observations,
            start=1
        ):

            with st.expander(
                f"Observation {index}",
                expanded=False
            ):

                st.markdown(
                    observation
                )

    else:

        st.warning(
            "No observations were collected."
        )


    # ========================================================
    # FINAL REPORT
    # ========================================================

    st.header("📄 Final Report")


    final_result = result.get(
        "final_result",
        "No final report was generated."
    )


    st.markdown(
        final_result
    )


    # ========================================================
    # DOWNLOAD FINAL REPORT
    # ========================================================

    st.download_button(
        label="⬇️ Download Final Report (Markdown)",
        data=final_result,
        file_name="agent_final_report.md",
        mime="text/markdown",
        type="primary"
    )


    # ========================================================
    # DOWNLOAD EXECUTION LOGS
    # ========================================================

    st.subheader("📥 Download Execution Logs")


    logs_text = "\n\n".join(
        [
            f"[{entry['type'].upper()}] "
            f"{entry['message']}"
            for entry in logs
        ]
    )


    st.download_button(
        label="Download Logs (.txt)",
        data=logs_text,
        file_name="agent_execution_logs.txt",
        mime="text/plain"
    )


    # ========================================================
    # COMPLETE EXECUTION LOG
    # ========================================================

    st.header("📝 Complete Execution Trace")


    with st.expander(
        "View all execution events",
        expanded=False
    ):

        for entry in logs:

            event_type = entry.get(
                "type",
                "info"
            ).upper()

            message = entry.get(
                "message",
                ""
            )


            st.markdown(
                f"**[{event_type}]**"
            )


            # Display plan JSON nicely
            if event_type == "PLAN":

                try:

                    parsed_plan = json.loads(message)

                    st.json(parsed_plan)

                except Exception:

                    st.code(
                        message,
                        language="text"
                    )

            else:

                st.write(message)


    # ========================================================
    # RESET BUTTON
    # ========================================================

    st.divider()


    if st.button(
        "🔄 Start a New Task",
        use_container_width=True
    ):

        st.session_state.agent_result = None

        st.session_state.execution_logs = []

        st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.divider()


st.caption(
    "Autonomous AI Research Agent | "
    "Powered by Gemini, Tavily, Python & Streamlit"
)
