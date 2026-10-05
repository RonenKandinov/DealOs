"""Referential checks for a ground-truth world. Relations must point at stored objects."""

from __future__ import annotations

from dealos.macro_world.models import GroundTruth


def integrity_errors(world: GroundTruth) -> tuple[str, ...]:
    errors: list[str] = []
    departments = {row.department_id for row in world.departments}
    roles = {row.role_id for row in world.roles}
    resources = {row.resource_id for row in world.resources}
    systems = {row.system_id for row in world.systems}
    deals = {row.deal_id for row in world.deals}
    tasks = {row.task_id for row in world.task_types}
    occurrences = {row.occurrence_id for row in world.occurrences}
    information = {row.information_id for row in world.information}
    organizations = {world.organization.organization_id}

    for department in world.departments:
        if department.organization_id not in organizations:
            errors.append(f"department {department.department_id} has an unknown organization")
    for role in world.roles:
        if role.department_id not in departments:
            errors.append(f"role {role.role_id} has an unknown department")
    for resource in world.resources:
        if resource.role_id and resource.role_id not in roles:
            errors.append(f"resource {resource.resource_id} has an unknown role")
        if resource.role_id and (resource.resource_id, resource.role_id) not in world.belongs_resource_role:
            errors.append(f"resource {resource.resource_id} role is missing from belongs_to")
    for occurrence in world.occurrences:
        if occurrence.deal_id not in deals:
            errors.append(f"occurrence {occurrence.occurrence_id} has an unknown deal")
        if occurrence.task_id not in tasks:
            errors.append(f"occurrence {occurrence.occurrence_id} has an unknown task type")
        if not 0.0 <= occurrence.progress <= 1.0:
            errors.append(f"occurrence {occurrence.occurrence_id} progress is outside [0, 1]")
    for info in world.information:
        if info.producer_system_id not in systems:
            errors.append(f"information {info.information_id} has an unknown producer")
        for consumer in info.consumer_system_ids:
            if consumer not in systems:
                errors.append(f"information {info.information_id} has an unknown consumer")
        if (info.producer_system_id, info.information_id) not in world.produces:
            errors.append(f"information {info.information_id} producer is missing from produces")
        for consumer in info.consumer_system_ids:
            if (consumer, info.information_id) not in world.consumes:
                errors.append(f"information {info.information_id} consumer is missing from consumes")
    for rule in world.authority_rules:
        if rule.holder_kind == "role" and rule.holder_id not in roles:
            errors.append(f"authority {rule.authority_id} has an unknown role")
        elif rule.holder_kind == "resource" and rule.holder_id not in resources:
            errors.append(f"authority {rule.authority_id} has an unknown resource")
        elif rule.holder_kind not in {"role", "resource"}:
            errors.append(f"authority {rule.authority_id} has an unknown holder kind")
        if not rule.action:
            errors.append(f"authority {rule.authority_id} has an empty action")
        if (rule.holder_id, rule.action) not in world.authorizes:
            errors.append(f"authority {rule.authority_id} is missing from authorizes")
    for pool in world.capacity_pools:
        if pool.capacity < 0:
            errors.append(f"capacity pool {pool.capacity_pool_id} is negative")
        if not pool.resource_id and not pool.role_id:
            errors.append(f"capacity pool {pool.capacity_pool_id} has no holder")
        if pool.resource_id and pool.resource_id not in resources:
            errors.append(f"capacity pool {pool.capacity_pool_id} has an unknown resource")
        if pool.role_id and pool.role_id not in roles:
            errors.append(f"capacity pool {pool.capacity_pool_id} has an unknown role")

    _pairs(errors, "belongs_to resource", world.belongs_resource_role, resources, roles)
    _pairs(errors, "belongs_to role", world.belongs_role_department, roles, departments)
    _pairs(errors, "performs", world.performs, resources, occurrences)
    _pairs(errors, "requires", world.requires, occurrences, information)
    _pairs(errors, "produces", world.produces, systems, information)
    _pairs(errors, "consumes", world.consumes, systems, information)
    holders = roles | resources
    _pairs(errors, "authorizes", world.authorizes, holders, None)
    _pairs(errors, "allocated_to", world.allocated_to, resources, occurrences)
    _pairs(errors, "depends_on", world.depends_on, tasks, tasks)
    return tuple(errors)


def _pairs(
    errors: list[str],
    label: str,
    pairs: tuple[tuple[str, str], ...],
    left: set[str],
    right: set[str] | None,
) -> None:
    for source, target in pairs:
        if source not in left:
            errors.append(f"{label} source {source} is unknown")
        if right is not None and target not in right:
            errors.append(f"{label} target {target} is unknown")
        if right is None and not target:
            errors.append(f"{label} target is empty")
