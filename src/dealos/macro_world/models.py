"""Synthetic macro-world records. These are not the simulator's Task or TaskOccurrence."""

from __future__ import annotations

from dataclasses import dataclass

R_MICRO = frozenset({"TaskType", "DAG", "TaskOccurrence", "Lifecycle", "Progress", "Capacity"})
R0_EXTRA = frozenset({"PersistentResourceIdentifier", "ResourceOccurrenceAssociation"})
CANDIDATE_PRIMITIVES = frozenset(
    {
        "PersistentResourceIdentifier",
        "ResourceOccurrenceAssociation",
        "Role",
        "Department",
        "ResourceRoleAssociation",
        "RoleDepartmentAssociation",
        "Authority",
        "InformationObject",
        "InformationDependency",
        "System",
        "SystemInformationRelation",
        "ResourceResourceRelation",
        "ResourceGroup",
    }
)
OPERATORS = frozenset({"AddObject", "AddRelation", "AddState", "AddAttribute"})
FORBIDDEN_IMPLICIT = frozenset({"person", "employee", "ownership", "handoff", "responsibility"})
FACT = "FACT"
HYPOTHESIS = "HYPOTHESIS"
INFERENCE = "INFERENCE"


@dataclass(frozen=True)
class Organization:
    organization_id: str


@dataclass(frozen=True)
class Department:
    department_id: str
    organization_id: str
    name: str


@dataclass(frozen=True)
class Role:
    role_id: str
    department_id: str
    name: str


@dataclass(frozen=True)
class Resource:
    resource_id: str
    role_id: str
    resource_type: str


@dataclass(frozen=True)
class System:
    system_id: str
    name: str


@dataclass(frozen=True)
class Deal:
    deal_id: str


@dataclass(frozen=True)
class TaskType:
    task_id: str
    name: str


@dataclass(frozen=True)
class TaskOccurrence:
    occurrence_id: str
    deal_id: str
    task_id: str
    lifecycle: str
    progress: float


@dataclass(frozen=True)
class InformationObject:
    information_id: str
    name: str
    producer_system_id: str
    consumer_system_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuthorityRule:
    authority_id: str
    holder_id: str
    holder_kind: str
    action: str
    scope: str


@dataclass(frozen=True)
class CapacityPool:
    capacity_pool_id: str
    resource_id: str
    role_id: str
    capacity: float


@dataclass(frozen=True)
class Trace:
    """One ground-truth event before masking. Hidden fields stay on this record."""

    event_id: str
    deal_id: str
    activity: str
    lifecycle: str
    resource_id: str
    system_id: str = ""
    information_id: str = ""
    role_id: str = ""
    department_id: str = ""
    authority: str = ""
    capacity: str = ""


@dataclass(frozen=True)
class GroundTruth:
    organization: Organization
    departments: tuple[Department, ...] = ()
    roles: tuple[Role, ...] = ()
    resources: tuple[Resource, ...] = ()
    systems: tuple[System, ...] = ()
    deals: tuple[Deal, ...] = ()
    task_types: tuple[TaskType, ...] = ()
    occurrences: tuple[TaskOccurrence, ...] = ()
    information: tuple[InformationObject, ...] = ()
    authority_rules: tuple[AuthorityRule, ...] = ()
    capacity_pools: tuple[CapacityPool, ...] = ()
    belongs_resource_role: tuple[tuple[str, str], ...] = ()
    belongs_role_department: tuple[tuple[str, str], ...] = ()
    performs: tuple[tuple[str, str], ...] = ()
    requires: tuple[tuple[str, str], ...] = ()
    produces: tuple[tuple[str, str], ...] = ()
    consumes: tuple[tuple[str, str], ...] = ()
    authorizes: tuple[tuple[str, str], ...] = ()
    allocated_to: tuple[tuple[str, str], ...] = ()
    depends_on: tuple[tuple[str, str], ...] = ()
    traces: tuple[Trace, ...] = ()


@dataclass(frozen=True)
class ObservationMask:
    expose_resource_id: bool = True
    expose_role: bool = False
    expose_department: bool = False
    expose_authority: bool = False
    expose_information_links: bool = False
    expose_system_id: bool = False
    expose_information_id: bool = False
    expose_capacity: bool = False
    expose_deal_id: bool = True
    expose_activity: bool = True
    expose_lifecycle: bool = True
    expose_timestamp: bool = True


@dataclass(frozen=True)
class Observation:
    """Fields that the mask copied. A missing key was not exposed."""

    event_id: str
    values: tuple[tuple[str, str], ...]

    def get(self, key: str) -> str | None:
        for name, value in self.values:
            if name == key:
                return value
        return None

    def fields(self) -> frozenset[str]:
        return frozenset(name for name, _value in self.values)


@dataclass(frozen=True)
class Representation:
    representation_id: str
    primitives: frozenset[str]

    def with_primitives(self, names: tuple[str, ...] | frozenset[str], candidate_id: str) -> Representation:
        return Representation(candidate_id, self.primitives | frozenset(names))


@dataclass(frozen=True)
class Mutation:
    operator: str
    target: str


@dataclass(frozen=True)
class Mismatch:
    mismatch_id: str
    evidence: str
    missing_capability: str
    epistemic_status: str
    affected_objects: tuple[str, ...]
    candidate_mutations: tuple[str, ...]


def micro_representation() -> Representation:
    return Representation("R_micro", R_MICRO)


def r0_representation() -> Representation:
    return Representation("R0", R_MICRO | R0_EXTRA)
