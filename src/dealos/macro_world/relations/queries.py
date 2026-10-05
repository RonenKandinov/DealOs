"""Representable, recoverable, and interpretable are three separate questions."""

from __future__ import annotations

from dealos.macro_world.models import Representation
from dealos.macro_world.relations.models import (
    REQUIREMENTS,
    TYPED_RESOURCE,
    MacroWorld,
    RelationMask,
    RelationObservation,
)


def representable(representation: Representation, relation_name: str) -> bool:
    return REQUIREMENTS[relation_name] <= representation.primitives


def recoverable(observations: tuple[RelationObservation, ...], mask: RelationMask, relation_name: str) -> bool:
    """True only when the mask exposes the endpoints and, for a typed link, the type itself."""

    if relation_name == "resource_role":
        return mask.expose_resource_id and mask.expose_role and _present(observations, "role_id")
    if relation_name == "role_department":
        return mask.expose_role and mask.expose_department and _present(observations, "department_id")
    if relation_name == "department_organization":
        return mask.expose_department and mask.expose_organization and _present(observations, "organization_id")
    if relation_name in TYPED_RESOURCE:
        return mask.expose_relation_type and _present(observations, "relation_type")
    if relation_name in {"role_authority", "resource_authority"}:
        return mask.expose_authority and mask.expose_holder_kind and _present(observations, "holder_kind")
    if relation_name == "system_produces_information":
        return mask.expose_information and mask.expose_system_id and _present(observations, "information_id")
    if relation_name == "information_consumed_by_system":
        return mask.expose_information and mask.expose_system_id and _present(observations, "information_id")
    if relation_name == "system_system":
        return False
    if relation_name in {"resource_capacity", "role_capacity", "department_capacity"}:
        return (
            mask.expose_capacity_pool
            and mask.expose_capacity_holder
            and _present(observations, "capacity_holder_kind")
        )
    return False


def interpretable(mask: RelationMask, relation_name: str) -> bool:
    """Co-occurrence and event order do not name the kind of relation."""

    if relation_name in TYPED_RESOURCE:
        return mask.expose_relation_type
    if relation_name == "system_system":
        return False
    if relation_name in {"role_authority", "resource_authority"}:
        return mask.expose_authority and mask.expose_holder_kind
    if relation_name in {"resource_capacity", "role_capacity", "department_capacity"}:
        return mask.expose_capacity_holder
    return True


def gt_has(world: MacroWorld, relation_name: str) -> bool:
    return any(relation.name == relation_name for relation in world.relations)


def activity_is_not_a_role(observations: tuple[RelationObservation, ...]) -> bool:
    blocked = {"LegalReviewer", "SecurityReviewer", "FinanceApprover", "Legal", "Security"}
    return all(observation.get("activity") not in blocked for observation in observations)


def _present(observations: tuple[RelationObservation, ...], key: str) -> bool:
    return any(observation.get(key) for observation in observations)
