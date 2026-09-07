"""Confidence intervals for adherence proportions — so no rule is cut on noise."""

from __future__ import annotations

import math

Z_95 = 1.96


def wilson(successes: float, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a proportion; (0.0, 1.0) when there are no observations."""
    if n <= 0:
        return 0.0, 1.0
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe_diff(
    successes_a: float, n_a: int, successes_b: float, n_b: int, z: float = Z_95
) -> tuple[float, float]:
    """Newcombe hybrid-score interval for the difference of two independent proportions."""
    if n_a <= 0 or n_b <= 0:
        return -1.0, 1.0
    p_a, p_b = successes_a / n_a, successes_b / n_b
    lo_a, hi_a = wilson(successes_a, n_a, z)
    lo_b, hi_b = wilson(successes_b, n_b, z)
    diff = p_a - p_b
    lo = diff - math.hypot(p_a - lo_a, hi_b - p_b)
    hi = diff + math.hypot(hi_a - p_a, p_b - lo_b)
    return max(-1.0, lo), min(1.0, hi)


def trials_for_halfwidth(halfwidth: float, z: float = Z_95) -> int:
    """Observations per arm needed for a worst-case (p=0.5) interval no wider than ±halfwidth."""
    if halfwidth <= 0:
        raise ValueError(_HALFWIDTH_POSITIVE)
    return math.ceil((z * z * 0.25) / (halfwidth * halfwidth))


_HALFWIDTH_POSITIVE = "halfwidth must be > 0"
