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

    # Sort tasks: Fixed by time, then flexible
    sorted_tasks = sorted(tasks, key=lambda x: x.req_start_time if x.req_start_time else datetime.max)

    # 1. Apply the delay to the first task in the list (the one currently happening)
    if sorted_tasks:
        sorted_tasks[0].true_duration = sorted_tasks[0].ideal_duration + active_task_delay

    # Set initial time
    first_fixed = next((t for t in sorted_tasks if t.req_start_time), None)
    current_time = first_fixed.req_start_time if first_fixed else datetime.now()

    for i, task in enumerate(sorted_tasks):
        # Anchor handling
        if task.req_start_time:
            task.scheduled_start = task.req_start_time
            # Only change current_time if this anchor starts AFTER our current progression
            current_time = max(current_time, task.req_start_time + task.true_duration)
        else:
            # Flexible handling
            task.scheduled_start = current_time

            # SQUEEZE LOGIC: Look ahead for the next Fixed Anchor
            next_anchor = next((t for t in sorted_tasks[i + 1:] if t.req_start_time), None)

            if next_anchor:
                # If this task pushes us past the next anchor, it must shrink
                if current_time + task.true_duration > next_anchor.req_start_time:
                    available_gap = next_anchor.req_start_time - current_time
                    # Don't let it shrink below the explicit min_duration
                    task.true_duration = max(task.min_duration, available_gap)

            current_time += task.true_duration

    return sorted_tasks