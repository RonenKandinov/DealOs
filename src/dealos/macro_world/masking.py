"""Copy a ground-truth trace into an observation. Hidden fields are omitted."""

from __future__ import annotations

from dealos.macro_world.models import Observation, ObservationMask, Trace


def apply_mask(trace: Trace, mask: ObservationMask, seed: int, index: int) -> Observation:
    values: list[tuple[str, str]] = [("event_id", trace.event_id)]
    if mask.expose_timestamp:
        values.append(("timestamp", f"{seed}:{index:04d}"))
    if mask.expose_deal_id and trace.deal_id:
        values.append(("deal_id", trace.deal_id))
    if mask.expose_activity and trace.activity:
        values.append(("activity", trace.activity))
    if mask.expose_lifecycle and trace.lifecycle:
        values.append(("lifecycle", trace.lifecycle))
    if mask.expose_resource_id and trace.resource_id:
        values.append(("resource_id", trace.resource_id))
    if mask.expose_system_id and trace.system_id:
        values.append(("system_id", trace.system_id))
    if mask.expose_information_id and trace.information_id:
        values.append(("information_id", trace.information_id))
    if mask.expose_role and trace.role_id:
        values.append(("role_id", trace.role_id))
    if mask.expose_department and trace.department_id:
        values.append(("department_id", trace.department_id))
    if mask.expose_authority and trace.authority:
        values.append(("authority", trace.authority))
    if mask.expose_information_links and trace.information_id:
        values.append(("information_link", trace.information_id))
    if mask.expose_capacity and trace.capacity:
        values.append(("capacity", trace.capacity))
    return Observation(trace.event_id, tuple(values))
