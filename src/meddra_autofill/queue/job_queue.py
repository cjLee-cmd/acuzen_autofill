"""Simple in-memory job queue for orchestration."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

from ..models import CaseRecord


@dataclass(slots=True)
class JobItem:
    record: CaseRecord
    attempts: int = 0
    max_attempts: int = 3
    error_messages: List[str] = field(default_factory=list)

    @property
    def is_exhausted(self) -> bool:
        return self.attempts >= self.max_attempts


class JobQueue:
    """A FIFO queue with retry bookkeeping."""

    def __init__(self) -> None:
        self._queue: Deque[JobItem] = deque()
        self._dead_letter: List[JobItem] = []

    def enqueue(self, record: CaseRecord) -> None:
        self._queue.append(JobItem(record=record))

    def dequeue(self) -> Optional[JobItem]:
        if not self._queue:
            return None
        return self._queue.popleft()

    def requeue(self, job: JobItem, error_message: str) -> None:
        job.attempts += 1
        job.error_messages.append(error_message)
        if job.is_exhausted:
            self._dead_letter.append(job)
        else:
            self._queue.append(job)

    @property
    def dead_letter(self) -> List[JobItem]:
        return list(self._dead_letter)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._queue)


__all__ = ["JobQueue", "JobItem"]
