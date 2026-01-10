import streamlit as st
from ScheduleManager import Task, run_optimization
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
st.title("⚡ Project Optimizer")

if 'task_list' not in st.session_state:
    st.session_state.task_list = []

# --- INPUT SECTION ---
with st.sidebar:
    st.header("New Task")
    name = st.text_input("Name")
    is_fixed = st.checkbox("Fixed Time?")

    col1, col2 = st.columns(2)
    with col1:
        ideal = st.number_input("Ideal (m)", 15, 480, 60)
        prio = st.slider("Priority", 0.0, 1.0, 0.7)
    with col2:
        min_t = st.number_input("Min (m)", 5, 480, 30)
        start_t = st.time_input("Start")

    if st.button("Add Task"):
        new_t = Task(
            id=str(len(st.session_state.task_list)),
            name=name,
            ideal_duration=timedelta(minutes=ideal),
            priority=prio,
            min_duration=timedelta(minutes=min_t),
            multitaskable=False,
            location="Remote",
            req_start_time=datetime.combine(datetime(2026, 1, 10), start_t) if is_fixed else None
        )
        st.session_state.task_list.append(new_t)
        st.rerun()

# --- OPTIMIZATION & DISPLAY ---
if st.session_state.task_list:
    st.subheader("🚨 Real-Time Adjustment")
    # This slider simulates a delay on the task currently in progress
    delay_mins = st.slider("Current Task Delay (minutes)", 0, 120, 0)
    delay_delta = timedelta(minutes=delay_mins)

    # --- RUN OPTIMIZATION ---
    optimized_schedule = run_optimization(st.session_state.task_list, active_task_delay=delay_delta)

    # --- DISPLAY ---
    st.write("### Your Adjusted Schedule")
    for t in optimized_schedule:
        st_time = t.scheduled_start.strftime("%H:%M")
        end_time = (t.scheduled_start + t.true_duration).strftime("%H:%M")

        # UI Feedback: Change color if task is at its minimum duration
        is_squeezed = t.true_duration <= t.min_duration and not t.req_start_time
        box_color = "#ffebee" if is_squeezed else "#e8f5e9"

        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            c1.metric("Time", f"{st_time}")
            with c2:
                st.markdown(f"""
                        <div style="background-color:{box_color}; padding:10px; border-radius:5px; color:black;">
                            <b>{t.name}</b> | {int(t.true_duration.total_seconds() / 60)}m 
                            {'(MINIMAL)' if is_squeezed else ''}
                        </div>
                    """, unsafe_allow_html=True)
                if t.req_start_time: st.caption("📍 Fixed Anchor")