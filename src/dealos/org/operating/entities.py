"""Organizational entities and first-class relations.

A field on one entity does not imply another relation. Resource is not a person.
Role is not authority. Participation is not a grant.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Organization:
    """A boundary. external marks outside that boundary. It is not a customer type."""

    organization_id: str
    external: bool = False


@dataclass(frozen=True)
class BusinessUnit:
    business_unit_id: str
    organization_id: str


@dataclass(frozen=True)
class Department:
    department_id: str
    organization_id: str


@dataclass(frozen=True)
class Team:
    team_id: str


@dataclass(frozen=True)
class Person:
    """A human actor. Holding a role or being a resource requires its own relation."""

    person_id: str


@dataclass(frozen=True)
class Role:
    role_id: str
    department_id: str


@dataclass(frozen=True)
class Capability:
    capability_id: str
    name: str


@dataclass(frozen=True)
class Accountability:
    accountability_id: str
    holder_id: str
    statement: str


@dataclass(frozen=True)
class DecisionRight:
    """Participation in a decision. The kind is not an authority grant."""

    right_id: str
    holder_id: str
    decision_id: str
    kind: str


@dataclass(frozen=True)
class Resource:
    """An allocatable id. It is not an employee and it has no manager."""

    resource_id: str


@dataclass(frozen=True)
class CapacityPool:
    pool_id: str
    total: float
    available: float


@dataclass(frozen=True)
class Responsibility:
    responsibility_id: str
    role_id: str
    statement: str


@dataclass(frozen=True)
class Decision:
    decision_id: str
    action: str
    status: str = "open"


@dataclass(frozen=True)
class AuthorityGrant:
    grant_id: str
    holder_id: str
    holder_kind: str
    decision_id: str


@dataclass(frozen=True)
class Delegation:
    delegation_id: str
    from_holder_id: str
    to_holder_id: str
    decision_id: str
    active: bool = True


@dataclass(frozen=True)
class Veto:
    veto_id: str
    holder_id: str
    decision_id: str
    active: bool = True


@dataclass(frozen=True)
class InformationObject:
    information_id: str
    available: bool = False


@dataclass(frozen=True)
class GovernanceBody:
    body_id: str
    member_role_ids: frozenset[str] = field(default_factory=frozenset)
    mandate: str = ""
    quorum: int = 0


@dataclass(frozen=True)
class EscalationRule:
    rule_id: str
    from_role_id: str
    to_role_id: str
    condition: str


@dataclass(frozen=True)
class Escalation:
    escalation_id: str
    rule_id: str
    subject_id: str
    open: bool = True


@dataclass(frozen=True)
class SLA:
    sla_id: str
    subject_id: str
    deadline: int
    breached: bool = False


@dataclass(frozen=True)
class Process:
    process_id: str
    name: str


@dataclass(frozen=True)
class System:
    system_id: str
    organization_id: str


@dataclass(frozen=True)
class ExternalRelation:
    relation_id: str
    external_organization_id: str
    internal_organization_id: str
    information_id: str
    kind: str = ""
    context_id: str = ""


@dataclass(frozen=True)
class Relation:
    """One configured link. The name is the whole meaning."""

    relation_id: str
    name: str
    source_id: str
    target_id: str


@dataclass(frozen=True)
class TaskConstraint:
    """An explicit macro requirement on one micro task. It is not inferred."""

    task_id: str
    capacity_pool_id: str | None = None
    information_id: str | None = None
    decision_id: str | None = None
    external_relation_id: str | None = None
    ready: bool = True
