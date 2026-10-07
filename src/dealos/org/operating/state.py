"""O_t and the configured relations that must stay referentially valid."""

from __future__ import annotations

from dataclasses import dataclass, field

from dealos.org.operating.entities import (
    AuthorityGrant,
    CapacityPool,
    Decision,
    Delegation,
    Department,
    Escalation,
    EscalationRule,
    ExternalRelation,
    GovernanceBody,
    InformationObject,
    Organization,
    Process,
    Relation,
    Resource,
    Responsibility,
    Role,
    SLA,
    System,
    TaskConstraint,
    Team,
    Veto,
    Accountability,
    BusinessUnit,
    Capability,
    DecisionRight,
    Person,
)


@dataclass
class OrgState:
    """O_t. Each component is stored. None is derived from another."""

    time: int = 0
    organizations: dict[str, Organization] = field(default_factory=dict)
    business_units: dict[str, BusinessUnit] = field(default_factory=dict)
    departments: dict[str, Department] = field(default_factory=dict)
    teams: dict[str, Team] = field(default_factory=dict)
    people: dict[str, Person] = field(default_factory=dict)
    roles: dict[str, Role] = field(default_factory=dict)
    capabilities: dict[str, Capability] = field(default_factory=dict)
    resources: dict[str, Resource] = field(default_factory=dict)
    capacity: dict[str, CapacityPool] = field(default_factory=dict)
    responsibilities: dict[str, Responsibility] = field(default_factory=dict)
    accountabilities: dict[str, Accountability] = field(default_factory=dict)
    decisions: dict[str, Decision] = field(default_factory=dict)
    decision_rights: dict[str, DecisionRight] = field(default_factory=dict)
    authority: dict[str, AuthorityGrant] = field(default_factory=dict)
    delegations: dict[str, Delegation] = field(default_factory=dict)
    vetoes: dict[str, Veto] = field(default_factory=dict)
    information: dict[str, InformationObject] = field(default_factory=dict)
    governance: dict[str, GovernanceBody] = field(default_factory=dict)
    escalation_rules: dict[str, EscalationRule] = field(default_factory=dict)
    escalations: dict[str, Escalation] = field(default_factory=dict)
    slas: dict[str, SLA] = field(default_factory=dict)
    processes: dict[str, Process] = field(default_factory=dict)
    systems: dict[str, System] = field(default_factory=dict)
    external_relations: dict[str, ExternalRelation] = field(default_factory=dict)
    relations: dict[str, Relation] = field(default_factory=dict)
    constraints: dict[str, TaskConstraint] = field(default_factory=dict)


def integrity_errors(state: OrgState) -> tuple[str, ...]:
    errors: list[str] = []
    for department in state.departments.values():
        if department.organization_id not in state.organizations:
            errors.append(f"department {department.department_id} has an unknown organization")
    for unit in state.business_units.values():
        if unit.organization_id not in state.organizations:
            errors.append(f"business unit {unit.business_unit_id} has an unknown organization")
    for role in state.roles.values():
        if role.department_id not in state.departments:
            errors.append(f"role {role.role_id} has an unknown department")
    for pool in state.capacity.values():
        if pool.available < -1e-9 or pool.available > pool.total + 1e-9:
            errors.append(f"capacity {pool.pool_id} is outside [0, total]")
    for grant in state.authority.values():
        if grant.holder_kind not in {"role", "resource", "governance"}:
            errors.append(f"grant {grant.grant_id} has an unknown holder kind")
        if grant.decision_id not in state.decisions:
            errors.append(f"grant {grant.grant_id} has an unknown decision")
    for relation in state.relations.values():
        if not relation.source_id or not relation.target_id or not relation.name:
            errors.append(f"relation {relation.relation_id} is incomplete")
    return tuple(errors)
