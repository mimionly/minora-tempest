"""
Rescue Queue — Priority-Ordered Task Manager
==============================================

A min-heap based priority queue that maintains rescue tasks
in urgency order. Supports dynamic insertion, re-prioritization,
and task completion.

The AI Rescue Agent (Person 3) pulls tasks from this queue
and assigns resources via the dispatch system.
"""

import heapq
from typing import List, Optional, Dict

from optimization.types import RescueTask, UrgencyLevel


class RescueQueue:
    """
    Priority queue for rescue operations.

    Uses a max-heap (negated scores) so the most urgent task
    is always at the top.

    Thread-safety note: This is NOT thread-safe. Person 3 should
    wrap calls in a lock if using from async context.
    """

    def __init__(self):
        self._heap: List[tuple] = []  # (-score, counter, task)
        self._counter: int = 0
        self._task_map: Dict[str, RescueTask] = {}  # incident_id → task
        self._removed: set = set()  # incident_ids that were removed

    @property
    def size(self) -> int:
        """Number of active tasks in the queue."""
        return len(self._task_map)

    @property
    def is_empty(self) -> bool:
        return self.size == 0

    def push(self, task: RescueTask) -> None:
        """
        Add a rescue task to the queue.
        If the incident already exists, it is re-prioritized.
        """
        if task.incident_id in self._task_map:
            self.remove(task.incident_id)

        entry = (-task.urgency_score, self._counter, task)
        self._counter += 1
        heapq.heappush(self._heap, entry)
        self._task_map[task.incident_id] = task

    def pop(self) -> Optional[RescueTask]:
        """
        Remove and return the highest-priority rescue task.
        Returns None if queue is empty.
        """
        while self._heap:
            neg_score, counter, task = heapq.heappop(self._heap)

            if task.incident_id in self._removed:
                self._removed.discard(task.incident_id)
                continue

            if task.incident_id in self._task_map:
                del self._task_map[task.incident_id]
                return task

        return None

    def peek(self) -> Optional[RescueTask]:
        """
        View the highest-priority task without removing it.
        """
        while self._heap:
            neg_score, counter, task = self._heap[0]

            if task.incident_id in self._removed:
                heapq.heappop(self._heap)
                self._removed.discard(task.incident_id)
                continue

            if task.incident_id not in self._task_map:
                heapq.heappop(self._heap)
                continue

            return task

        return None

    def remove(self, incident_id: str) -> bool:
        """
        Mark a task as removed (lazy deletion).
        Returns True if the task was found and removed.
        """
        if incident_id in self._task_map:
            del self._task_map[incident_id]
            self._removed.add(incident_id)
            return True
        return False

    def mark_resolved(self, incident_id: str) -> bool:
        """Mark an incident as resolved and remove from queue."""
        return self.remove(incident_id)

    def get_all_tasks(self) -> List[RescueTask]:
        """
        Return all active tasks sorted by urgency (highest first).
        Used by the frontend to display the rescue queue.
        """
        tasks = list(self._task_map.values())
        tasks.sort(key=lambda t: t.urgency_score, reverse=True)
        return tasks

    def get_critical_tasks(self) -> List[RescueTask]:
        """Return only CRITICAL urgency tasks."""
        return [
            t for t in self._task_map.values()
            if t.urgency_level == UrgencyLevel.CRITICAL
        ]

    def bulk_load(self, tasks: List[RescueTask]) -> None:
        """Load multiple tasks at once (initial queue setup)."""
        for task in tasks:
            self.push(task)

    def to_dict_list(self) -> List[dict]:
        """Serialize all tasks for JSON API response."""
        return [t.to_dict() for t in self.get_all_tasks()]
