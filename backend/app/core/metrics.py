"""
Lightweight in-memory metrics registry for RecoverAI.

Provides thread-safe atomic counters for operational monitoring and telemetry.
Designed to be swappable with Prometheus / OpenTelemetry collectors.
"""

from collections import defaultdict
import threading
from typing import Dict


class MetricsRegistry:
    """Thread-safe counter and telemetry tracker."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def increment(self, metric_name: str, value: int = 1) -> None:
        """Increment a named metric counter atomically."""
        with self._lock:
            self._counters[metric_name] += value

    def get_count(self, metric_name: str) -> int:
        """Get the current count for a specific metric."""
        with self._lock:
            return self._counters.get(metric_name, 0)

    def get_all_metrics(self) -> Dict[str, int]:
        """Return a snapshot of all active metrics."""
        with self._lock:
            return dict(self._counters)

    def reset(self) -> None:
        """Reset all counters (useful for isolated tests)."""
        with self._lock:
            self._counters.clear()


# Global application metrics singleton
metrics = MetricsRegistry()
