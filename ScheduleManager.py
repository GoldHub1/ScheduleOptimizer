from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List

@dataclass
class Task:
    id: str
    name: str
    ideal_duration: timedelta
    priority: float  # 0 to 1
    min_duration: timedelta
    multitaskable: bool
    location: str
    true_duration: timedelta = field(init=False)
    concurrent_tasks: List[str] = field(default_factory=list)
    req_start_time: Optional[datetime] = None
    req_end_time: Optional[datetime] = None

    # New fields for the engine to fill
    scheduled_start: Optional[datetime] = None
    is_active: bool = True  # To handle "dropping" tasks if they don't fit

    def __post_init__(self):
        self.true_duration = self.ideal_duration

    @property
    def can_shrink(self) -> bool:
        return self.true_duration > self.min_duration


    """
    The main algorithm:
    1. Sorts tasks
    2. Identifies overlaps with fixed anchors
    3. Shrinks flexible tasks based on priority
    """


def run_optimization(tasks: List[Task], active_task_delay: timedelta = timedelta(0)) -> List[Task]:
    if not tasks:
        return []

    now = datetime.now()

    # --- STEP 1: DRY RUN ---
    # We do a quick pass to see where tasks WOULD be without any new delay
    fixed_tasks = sorted([t for t in tasks if t.req_start_time], key=lambda x: x.req_start_time)
    flex_pool = sorted([t for t in tasks if not t.req_start_time], key=lambda x: x.priority, reverse=True)

    # We use a temporary schedule to find the target
    dry_run = execute_interleaved_filling(fixed_tasks, flex_pool)

    # --- STEP 2: FIND TARGET ---
    target_task = None

    # Look for the task happening RIGHT NOW in the dry run
    for t in dry_run:
        t_end = t.scheduled_start + t.ideal_duration
        if t.scheduled_start <= now <= t_end:
            target_task = t
            break

    # Fallback: If we are in a gap, find the very next task to start
    if not target_task:
        upcoming = [t for t in dry_run if t.scheduled_start > now]
        if upcoming:
            target_task = min(upcoming, key=lambda x: x.scheduled_start)

    # --- STEP 3: APPLY DELAY ---
    # Reset all true_durations to ideal first
    for t in tasks:
        t.true_duration = t.ideal_duration

    if target_task:
        target_task.true_duration += active_task_delay

    # --- STEP 4: FINAL RUN ---
    # Run the real interleaved filling with the delayed task
    return execute_interleaved_filling(fixed_tasks, flex_pool)


def execute_interleaved_filling(fixed_tasks: List[Task], flex_pool: List[Task]) -> List[Task]:
    """
    The actual 'Gap Filler'. It pours flexible tasks into the spaces
    between fixed anchors.
    """
    final_schedule = []
    # Use a copy of the flex pool so we don't destroy the original list
    remaining_flex = list(flex_pool)

    # Determine the start time (use the first fixed task's time or now)
    if fixed_tasks:
        current_time = min(fixed_tasks[0].req_start_time, datetime.now())
    else:
        current_time = datetime.now()

    for anchor in fixed_tasks:
        # While there is a gap before the next anchor...
        while remaining_flex:
            task = remaining_flex[0]

            # Can it fit in the gap?
            if current_time + task.true_duration <= anchor.req_start_time:
                task.scheduled_start = current_time
                final_schedule.append(remaining_flex.pop(0))
                current_time += task.true_duration
            # If it can't fit fully, can it be SQUEEZED?
            elif current_time + task.min_duration <= anchor.req_start_time:
                task.scheduled_start = current_time
                task.true_duration = anchor.req_start_time - current_time
                final_schedule.append(remaining_flex.pop(0))
                current_time = anchor.req_start_time
            else:
                # Doesn't fit in this gap, stop trying to fill it
                break

        # Place the Anchor
        anchor.scheduled_start = anchor.req_start_time
        final_schedule.append(anchor)
        current_time = anchor.req_start_time + anchor.true_duration

    # Add any leftover flex tasks at the end
    for task in remaining_flex:
        task.scheduled_start = current_time
        final_schedule.append(task)
        current_time += task.true_duration

    return sorted(final_schedule, key=lambda x: x.scheduled_start)
