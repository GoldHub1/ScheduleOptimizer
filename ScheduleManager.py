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

    #required start and end
    req_start_time: Optional[datetime] = None
    req_end_time: Optional[datetime] = None

    #Window Fields
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
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

    # 1. Reset all tasks to ideal durations for the calculation
    for t in tasks:
        t.true_duration = t.ideal_duration

    fixed_tasks = sorted([t for t in tasks if t.req_start_time], key=lambda x: x.req_start_time)
    flex_pool = sorted([t for t in tasks if not t.req_start_time], key=lambda x: x.priority, reverse=True)

    # 2. Dry Run to find the 'Active' task (no delay applied yet)
    # We use start_override=None (default) to see where things naturally land
    temp_sched = execute_interleaved_filling(fixed_tasks, flex_pool)

    target_task = None
    for t in temp_sched:
        t_end = t.scheduled_start + t.true_duration
        if t.scheduled_start <= now <= t_end:
            target_task = t
            break

    # 3. Setup the Ripple Effect
    start_search_from = now
    if target_task:
        # Apply the slider delay to the active task
        target_task.true_duration = target_task.ideal_duration + active_task_delay
        # THE KEY: The rest of the day must start AFTER the active task finishes
        start_search_from = target_task.scheduled_start + target_task.true_duration

        # Remove active task from pools so the engine doesn't duplicate it
        if target_task in fixed_tasks: fixed_tasks.remove(target_task)
        if target_task in flex_pool: flex_pool.remove(target_task)

    # 4. Final Run: Optimized the REMAINING tasks into the REMAINING time
    optimized_remaining = execute_interleaved_filling(
        fixed_tasks,
        flex_pool,
        start_override=start_search_from
    )

    # Combine the 'frozen' delayed task with the newly squeezed remainder
    final = ([target_task] if target_task else []) + optimized_remaining
    return sorted(final, key=lambda x: x.scheduled_start)


def execute_interleaved_filling(fixed_tasks: List[Task], flex_pool: List[Task],
                                start_override: Optional[datetime] = None) -> List[Task]:
    final_schedule = []
    remaining_flex = [t for t in flex_pool]
    anchors = sorted([t for t in fixed_tasks], key=lambda x: x.req_start_time)

    current_time = start_override if start_override else datetime.now()

    # Fallback End of Day anchor
    eod_time = current_time + timedelta(hours=12)
    if anchors:
        eod_time = max(eod_time, anchors[-1].req_start_time + anchors[-1].ideal_duration + timedelta(hours=4))

    all_anchors = anchors + [Task(id="eod", name="End of Day", ideal_duration=timedelta(0),
                                  priority=0, min_duration=timedelta(0), multitaskable=False,
                                  location="", req_start_time=eod_time)]

    for anchor in all_anchors:
        # Calculate available gap
        gap_end = anchor.req_start_time
        gap_duration = gap_end - current_time

        # 1. CANDIDATE SELECTION
        gap_candidates = []
        still_to_process = []

        # Only process the gap if it actually exists
        if gap_duration > timedelta(0):
            while remaining_flex:
                t = remaining_flex.pop(0)

                # Check Window Constraints
                too_late = t.window_start and t.window_start >= gap_end
                too_early = t.window_end and t.window_end <= current_time

                if too_late or too_early:
                    still_to_process.append(t)
                    continue

                # AGGRESSIVE CHECK: Can we fit this task at its MINIMUM?
                current_min_total = sum((c.min_duration for c in gap_candidates), timedelta())
                if current_min_total + t.min_duration <= gap_duration:
                    gap_candidates.append(t)
                else:
                    still_to_process.append(t)

        # Put skipped tasks back for the next anchor
        remaining_flex = still_to_process + remaining_flex

        # 2. LINEAR SQUEEZE WITH REDISTRIBUTION
        if gap_candidates:
            # Initial Squeeze
            total_ideal = sum((c.ideal_duration for c in gap_candidates), timedelta())
            if total_ideal > gap_duration:
                debt_secs = (total_ideal - gap_duration).total_seconds()
                weights = [(1.1 - c.priority) for c in gap_candidates]
                total_weight = sum(weights)

                for i, c in enumerate(gap_candidates):
                    share = weights[i] / total_weight
                    reduction = timedelta(seconds=debt_secs * share)
                    c.true_duration = max(c.min_duration, c.ideal_duration - reduction)

                # Redistribution Loop: Fixes the "84th minute" jump
                # Ensures we use every available second of the gap
                current_sum = sum((c.true_duration for c in gap_candidates), timedelta())
                for _ in range(5):  # Max 5 passes to reach stability
                    diff = (current_sum - gap_duration).total_seconds()
                    if abs(diff) < 1: break  # Close enough

                    shrinkable = [c for c in gap_candidates if c.true_duration > c.min_duration]
                    if not shrinkable: break

                    shave = diff / len(shrinkable)
                    for c in shrinkable:
                        c.true_duration = max(c.min_duration, c.true_duration - timedelta(seconds=shave))
                    current_sum = sum((c.true_duration for c in gap_candidates), timedelta())
            else:
                for c in gap_candidates:
                    c.true_duration = c.ideal_duration

            # 3. POSITIONING
            for c in gap_candidates:
                if c.window_start and current_time < c.window_start:
                    current_time = c.window_start

                c.scheduled_start = current_time
                final_schedule.append(c)

                if not c.multitaskable:
                    current_time += c.true_duration

        # 4. PLACE THE ANCHOR
        if anchor.id != "eod":
            anchor.scheduled_start = anchor.req_start_time
            final_schedule.append(anchor)
            # Anchor moves the cursor to its end
            current_time = anchor.req_start_time + anchor.ideal_duration

    return sorted(final_schedule, key=lambda x: x.scheduled_start)
