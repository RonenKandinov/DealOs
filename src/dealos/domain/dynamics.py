"""Deterministic one-step progress and status rules."""

from __future__ import annotations

from dealos.domain.models import TaskStatus


def delta_x(phi: float, ready: float, resource_terms: float) -> float:
    """Δx = φ * Ready * Σ_r α q a.

    `resource_terms` is the sum over resources. Readiness scales new progress
    and does not pull existing progress backward.
    """

    return phi * ready * resource_terms


def apply_progress(progress: float, delta: float, completion_tolerance: float) -> float:
    """x <- min(1, x + Δx), then snap to 1 within the completion tolerance."""

    updated = progress + delta
    if updated >= 1.0 - completion_tolerance:
        return 1.0
    if updated <= 0.0:
        return 0.0
    return updated


def is_complete(progress: float, completion_tolerance: float) -> bool:
    return progress >= 1.0 - completion_tolerance


def classify_status(
    progress: float,
    ready: float,
    *,
    blocked_readiness_threshold: float,
    completion_tolerance: float,
) -> TaskStatus:
    """Status is a function of progress and current readiness.

    BLOCKED means the task is incomplete and readiness is at or below the
    configured threshold, so the dynamics add no new progress. Partial
    predecessor progress (ready above the threshold) is not full blockage.
    """

    if is_complete(progress, completion_tolerance):
        return TaskStatus.COMPLETED
    if ready <= blocked_readiness_threshold:
        return TaskStatus.BLOCKED
    if progress <= 0.0:
        return TaskStatus.NOT_STARTED
    return TaskStatus.IN_PROGRESS
