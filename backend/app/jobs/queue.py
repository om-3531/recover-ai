"""
Background Job Queue abstraction.

Provides a pluggable queue interface with a deterministic in-process implementation
for offline unit tests and local development.
"""

from abc import ABC, abstractmethod
from collections import deque
from threading import Lock
from typing import Optional


class JobQueue(ABC):
    """Abstract interface for background job queues."""

    @abstractmethod
    def enqueue(self, job_id: int) -> None:
        """Enqueue a job ID for background processing."""
        pass

    @abstractmethod
    def dequeue(self) -> Optional[int]:
        """Dequeue the next job ID to be processed."""
        pass

    @abstractmethod
    def size(self) -> int:
        """Return the count of currently queued jobs."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all queued jobs (useful in testing)."""
        pass


class InMemoryJobQueue(JobQueue):
    """Thread-safe in-memory FIFO queue for local development and deterministic testing."""

    def __init__(self) -> None:
        self._queue: deque[int] = deque()
        self._lock = Lock()

    def enqueue(self, job_id: int) -> None:
        with self._lock:
            self._queue.append(job_id)

    def dequeue(self) -> Optional[int]:
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()


_default_queue = InMemoryJobQueue()


def get_default_job_queue() -> JobQueue:
    """Return the global default job queue."""
    return _default_queue
