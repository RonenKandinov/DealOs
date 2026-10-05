"""Project ground truth to the exposed event stream."""

from __future__ import annotations

from dealos.macro_world.masking import apply_mask
from dealos.macro_world.models import GroundTruth, Observation, ObservationMask, Trace


def observe(world: GroundTruth, mask: ObservationMask, seed: int) -> tuple[Observation, ...]:
    traces = tuple(sorted(world.traces, key=lambda trace: trace.event_id))
    return tuple(apply_mask(trace, mask, seed, index) for index, trace in enumerate(traces))


def leak_count(world: GroundTruth, observations: tuple[Observation, ...], mask: ObservationMask) -> int:
    """Count exposed values that the mask forbids or that disagree with the trace."""

    by_id = {trace.event_id: trace for trace in world.traces}
    leaks = 0
    if len(observations) != len(by_id):
        leaks += abs(len(observations) - len(by_id))
    for observation in observations:
        trace = by_id.get(observation.event_id)
        if trace is None:
            leaks += 1
            continue
        leaks += _row_leaks(trace, observation, mask)
    return leaks


def _row_leaks(trace: Trace, observation: Observation, mask: ObservationMask) -> int:
    expected = {
        "deal_id": (mask.expose_deal_id, trace.deal_id),
        "activity": (mask.expose_activity, trace.activity),
        "lifecycle": (mask.expose_lifecycle, trace.lifecycle),
        "resource_id": (mask.expose_resource_id, trace.resource_id),
        "system_id": (mask.expose_system_id, trace.system_id),
        "information_id": (mask.expose_information_id, trace.information_id),
        "role_id": (mask.expose_role, trace.role_id),
        "department_id": (mask.expose_department, trace.department_id),
        "authority": (mask.expose_authority, trace.authority),
        "information_link": (mask.expose_information_links, trace.information_id),
        "capacity": (mask.expose_capacity, trace.capacity),
    }
    leaks = 0
    for key, (exposed, truth) in expected.items():
        seen = observation.get(key)
        if exposed and truth:
            if seen != truth:
                leaks += 1
        elif seen is not None:
            leaks += 1
    return leaks
