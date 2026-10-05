"""Two separate questions: what a representation can express, and what an event stream shows."""

from __future__ import annotations

from collections import defaultdict

from dealos.macro_world.models import GroundTruth, Observation, ObservationMask, Representation

REQUIREMENTS = {
    "resource_occurrence_identity": frozenset(
        {"PersistentResourceIdentifier", "ResourceOccurrenceAssociation"}
    ),
    "role": frozenset({"Role", "ResourceRoleAssociation"}),
    "department": frozenset({"Department", "RoleDepartmentAssociation"}),
    "authority": frozenset({"Authority"}),
    "information_dependency": frozenset({"InformationObject", "InformationDependency"}),
    "shared_identity": frozenset({"PersistentResourceIdentifier", "ResourceOccurrenceAssociation"}),
    "capacity_pool": frozenset({"Capacity"}),
    "ambiguous_interpretation": frozenset(),
}


def representable(representation: Representation, capability: str) -> bool:
    if capability == "ambiguous_interpretation":
        return False
    required = REQUIREMENTS[capability]
    return required <= representation.primitives


def recoverable(observations: tuple[Observation, ...], mask: ObservationMask, capability: str) -> bool:
    """True only when the mask itself exposes the relation. Activity names are not roles or authority."""

    if capability == "resource_occurrence_identity" or capability == "shared_identity":
        return mask.expose_resource_id and mask.expose_deal_id and _cross_deal(observations)
    if capability == "role":
        return mask.expose_role and _present(observations, "role_id")
    if capability == "department":
        return mask.expose_department and _present(observations, "department_id")
    if capability == "authority":
        return mask.expose_authority and _present(observations, "authority")
    if capability == "information_dependency":
        return mask.expose_information_links and _present(observations, "information_link")
    if capability == "capacity_pool":
        return mask.expose_capacity and _present(observations, "capacity")
    if capability == "ambiguous_interpretation":
        return False
    return False


def authorized_holders(world: GroundTruth) -> frozenset[str]:
    return frozenset(holder for holder, _action in world.authorizes)


def performers_of_activity(world: GroundTruth, activity: str) -> frozenset[str]:
    task_ids = {task.task_id for task in world.task_types if task.name == activity or task.task_id == activity}
    occurrence_ids = {row.occurrence_id for row in world.occurrences if row.task_id in task_ids}
    return frozenset(resource_id for resource_id, occurrence_id in world.performs if occurrence_id in occurrence_ids)


def _cross_deal(observations: tuple[Observation, ...]) -> bool:
    deals: dict[str, set[str]] = defaultdict(set)
    for observation in observations:
        resource_id = observation.get("resource_id")
        deal_id = observation.get("deal_id")
        if resource_id and deal_id:
            deals[resource_id].add(deal_id)
    return any(len(ids) >= 2 for ids in deals.values())


def _present(observations: tuple[Observation, ...], key: str) -> bool:
    return any(observation.get(key) for observation in observations)
