"""Copy macro events through a mask. Hidden fields are omitted."""

from __future__ import annotations

from dealos.macro_world.relations.models import MacroEvent, MacroWorld, RelationMask, RelationObservation


def observe(world: MacroWorld, mask: RelationMask, seed: int) -> tuple[RelationObservation, ...]:
    events = tuple(sorted(world.events, key=lambda event: event.event_id))
    return tuple(_apply(event, mask, seed, index) for index, event in enumerate(events))


def leak_count(world: MacroWorld, observations: tuple[RelationObservation, ...], mask: RelationMask) -> int:
    by_id = {event.event_id: event for event in world.events}
    leaks = 0 if len(observations) == len(by_id) else abs(len(observations) - len(by_id))
    for observation in observations:
        event = by_id.get(observation.event_id)
        if event is None:
            leaks += 1
            continue
        leaks += _row_leaks(event, observation, mask)
    return leaks


def _apply(event: MacroEvent, mask: RelationMask, seed: int, index: int) -> RelationObservation:
    values: list[tuple[str, str]] = [("event_id", event.event_id)]
    if mask.expose_timestamp:
        values.append(("timestamp", f"{seed}:{index:04d}"))
    _copy(values, mask.expose_resource_id, "resource_id", event.resource_id)
    _copy(values, mask.expose_other_resource_id, "other_resource_id", event.other_resource_id)
    _copy(values, mask.expose_role, "role_id", event.role_id)
    _copy(values, mask.expose_department, "department_id", event.department_id)
    _copy(values, mask.expose_organization, "organization_id", event.organization_id)
    _copy(values, mask.expose_activity, "activity", event.activity)
    _copy(values, mask.expose_system_id, "system_id", event.system_id)
    _copy(values, mask.expose_information, "information_id", event.information_id)
    _copy(values, mask.expose_authority, "authority_holder", event.authority_holder)
    _copy(values, mask.expose_holder_kind, "holder_kind", event.holder_kind)
    _copy(values, mask.expose_relation_type, "relation_type", event.relation_type)
    _copy(values, mask.expose_capacity_pool, "capacity_pool_id", event.capacity_pool_id)
    _copy(values, mask.expose_capacity_holder, "capacity_holder_id", event.capacity_holder_id)
    _copy(values, mask.expose_capacity_holder, "capacity_holder_kind", event.capacity_holder_kind)
    return RelationObservation(event.event_id, tuple(values))


def _copy(values: list[tuple[str, str]], exposed: bool, key: str, truth: str) -> None:
    if exposed and truth:
        values.append((key, truth))


def _row_leaks(event: MacroEvent, observation: RelationObservation, mask: RelationMask) -> int:
    expected = {
        "resource_id": (mask.expose_resource_id, event.resource_id),
        "other_resource_id": (mask.expose_other_resource_id, event.other_resource_id),
        "role_id": (mask.expose_role, event.role_id),
        "department_id": (mask.expose_department, event.department_id),
        "organization_id": (mask.expose_organization, event.organization_id),
        "activity": (mask.expose_activity, event.activity),
        "system_id": (mask.expose_system_id, event.system_id),
        "information_id": (mask.expose_information, event.information_id),
        "authority_holder": (mask.expose_authority, event.authority_holder),
        "holder_kind": (mask.expose_holder_kind, event.holder_kind),
        "relation_type": (mask.expose_relation_type, event.relation_type),
        "capacity_pool_id": (mask.expose_capacity_pool, event.capacity_pool_id),
        "capacity_holder_id": (mask.expose_capacity_holder, event.capacity_holder_id),
        "capacity_holder_kind": (mask.expose_capacity_holder, event.capacity_holder_kind),
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
