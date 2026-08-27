"""
Mathematical and metrics calculation utilities for Recovery Analytics.
"""

from datetime import datetime, timezone
from typing import Optional, Union


def safe_division(
    numerator: Union[int, float],
    denominator: Union[int, float],
    max_val: Optional[float] = 1.0,
) -> float:
    """
    Safely computes division with zero-denominator protection and bounding.

    Args:
        numerator: Numerator value.
        denominator: Denominator value.
        max_val: Optional maximum ceiling for ratio bounding (defaults to 1.0).

    Returns:
        float: Bounded division result (rounded to 4 decimal places).
    """
    if not denominator or denominator <= 0:
        return 0.0

    ratio = float(numerator) / float(denominator)
    if max_val is not None:
        ratio = min(max_val, ratio)
    ratio = max(0.0, ratio)
    return round(ratio, 4)


def safe_average(total: Union[int, float], count: int) -> int:
    """
    Computes integer average without division-by-zero errors.

    Args:
        total: Sum of values (e.g. paise).
        count: Number of elements.

    Returns:
        int: Rounded integer average.
    """
    if not count or count <= 0:
        return 0
    return int(round(float(total) / float(count)))


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime object has UTC timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
