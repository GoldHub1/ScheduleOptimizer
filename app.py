import streamlit as st
from ScheduleManager import Task, run_optimization
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Project Optimizer", page_icon="⚡")
st.title("⚡ Project Optimizer")

# Initialize session state for the task list
if 'task_list' not in st.session_state:
    st.session_state.task_list = []

# --- 1. SIDEBAR: INPUT SECTION ---
with st.sidebar:
    st.header("New Task")
    name = st.text_input("Name", placeholder="e.g. Deep Work")
    is_fixed = st.checkbox("Fixed Time? (Anchor)")

    col1, col2 = st.columns(2)
    with col1:
        ideal = st.number_input("Ideal (m)", 15, 480, 60)
        prio = st.slider("Priority", 0.0, 1.0, 0.7)
    with col2:
        min_t = st.number_input("Min (m)", 5, 480, 30)
        start_t = st.time_input("Start Time")

    if st.button("Add Task", use_container_width=True):
        if name:
            # Generate a truly unique ID using high-precision timestamp
            unique_id = datetime.now().strftime("%Y%m%d%H%M%S%f")

            # Combine the selected time with TODAY'S date instead of a hardcoded past date
            current_date = datetime.now().date()
            start_datetime = datetime.combine(current_date, start_t) if is_fixed else None

            new_t = Task(
                id=unique_id,
                name=name,
                ideal_duration=timedelta(minutes=ideal),
                priority=prio,
                min_duration=timedelta(minutes=min_t),
                multitaskable=False,
                location="Remote",
                req_start_time=start_datetime
            )
            st.session_state.task_list.append(new_t)
            st.rerun()
        else:
            st.error("Please enter a task name.")

# --- 2. MAIN: OPTIMIZATION & DISPLAY ---
if st.session_state.task_list:
    st.divider()

    # STEP A: Create the Delay Slider first so we have the value
    delay_mins = st.slider("Additional Minutes to add to active task", 0, 120, 0)

    # STEP B: Run Optimization to calculate scheduled_start and true_duration
    # This must happen before we try to detect the "Active" task
    optimized_schedule = run_optimization(
        st.session_state.task_list,
        active_task_delay=timedelta(minutes=delay_mins)
    )

    # STEP C: Detect the Active Task based on the fresh optimization results
    active_task_name = "None (Gap)"
    now = datetime.now()

    for t in optimized_schedule:
        # Check if current clock time falls within the task's calculated window
        t_end = t.scheduled_start + t.true_duration
        if t.scheduled_start <= now <= t_end:
            active_task_name = t.name
            break

    st.subheader(f"🚨 Delaying Active Task: {active_task_name}")

    # STEP D: Display the Schedule
    st.write("### Your Adjusted Schedule")

    for t in optimized_schedule:
        st_time = t.scheduled_start.strftime("%H:%M")
        end_time = (t.scheduled_start + t.true_duration).strftime("%H:%M")

        # Visual Feedback: Red for squeezed tasks, Green for healthy ones
        is_squeezed = t.true_duration <= t.min_duration and not t.req_start_time
        box_color = "#ffebee" if is_squeezed else "#e8f5e9"

        with st.container(border=True):
            # c1: Time | c2: Task Info | c3: Delete Action
            c1, c2, c3 = st.columns([1, 4, 0.5])

            with c1:
                st.metric("Start", f"{st_time}")
                st.caption(f"Ends {end_time}")

            with c2:
                # Calculate Squeeze Metrics
                ideal_secs = t.ideal_duration.total_seconds()
                true_secs = t.true_duration.total_seconds()

                mins_lost = int((ideal_secs - true_secs) / 60)
                pct_of_ideal = (true_secs / ideal_secs) * 100 if ideal_secs > 0 else 100

                # Custom HTML for the Task Box
                st.markdown(f"""
                        <div style="background-color:{box_color}; padding:12px; border-radius:8px; border: 1px solid #ddd; color:black;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <strong style="font-size: 1.1rem; line-height: 1;">{t.name}</strong>
                                {"<span style='background: #ffcc00; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; border: 1px solid #d4af37;'>⚠ -" + str(mins_lost) + "m squeeze</span>" if mins_lost > 0 else "<span style='background: #4caf50; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold;'>✓ Full Time</span>"}
                            </div>
                            <div style="font-size: 0.85rem; color: #555; margin-bottom: 4px;">
                                Efficiency: {int(pct_of_ideal)}% of goal
                            </div>
                            <div style="height: 6px; width: 100%; background: #e0e0e0; border-radius: 3px; overflow: hidden;">
                                <div style="height: 100%; width: {pct_of_ideal}%; background: {'#f44336' if is_squeezed else '#4caf50'}; transition: width 0.5s ease-in-out;"></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                if t.req_start_time:
                    st.caption("📍 Fixed Anchor (Scheduled Start is Locked)")
                else:
                    st.caption(f"Flexible Task (Priority: {t.priority})")

            with c3:
                st.write("")  # Spacer to align with the box
                if st.button("🗑️", key=f"del_{t.id}", help="Delete this task"):
                    st.session_state.task_list = [task for task in st.session_state.task_list if task.id != t.id]
                    st.rerun()

else:
    # Empty state message
    st.info("Your schedule is empty. Add tasks via the sidebar to begin optimizing your day.")
    st.image("https://img.icons8.com/illustrations/complete/100/calendar.png", width=100)
