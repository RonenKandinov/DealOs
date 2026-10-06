"""Macro-to-macro relation records. These are not a bridge into the micro graph."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from dealos.macro_world.models import Representation

MACRO_R0 = frozenset({"PersistentResourceIdentifier", "ResourceOccurrenceAssociation"})
OPERATORS = frozenset({"AddObject", "AddRelation", "AddState", "AddAttribute"})
BRIDGE = frozenset({"TaskOccurrence", "TaskType", "Deal", "Task", "Allocation", "ResourceOccurrenceAssociation"})
FACT = "FACT"
INFERENCE = "INFERENCE"
HYPOTHESIS = "HYPOTHESIS"

def macro_r0() -> Representation:
    return Representation("R_macro_0", MACRO_R0)


@dataclass(frozen=True)
class MacroRelation:
    relation_id: str
    name: str
    source_id: str
    target_id: str
    semantic: str


@dataclass(frozen=True)
class MacroEvent:
    event_id: str
    order: int
    resource_id: str = ""
    other_resource_id: str = ""
    role_id: str = ""
    department_id: str = ""
    organization_id: str = ""
    activity: str = ""
    system_id: str = ""
    information_id: str = ""
    authority_holder: str = ""
    holder_kind: str = ""
    relation_type: str = ""
    capacity_pool_id: str = ""
    capacity_holder_id: str = ""
    capacity_holder_kind: str = ""


@dataclass(frozen=True)
class MacroWorld:
    relations: tuple[MacroRelation, ...]
    events: tuple[MacroEvent, ...]


@dataclass(frozen=True)
class RelationMask:
    expose_resource_id: bool = True
    expose_other_resource_id: bool = False
    expose_role: bool = False
    expose_department: bool = False
    expose_organization: bool = False
    expose_activity: bool = True
    expose_timestamp: bool = True
    expose_system_id: bool = False
    expose_information: bool = False
    expose_authority: bool = False
    expose_holder_kind: bool = False
    expose_relation_type: bool = False
    expose_capacity_pool: bool = False
    expose_capacity_holder: bool = False


@dataclass(frozen=True)
class RelationObservation:
    event_id: str
    values: tuple[tuple[str, str], ...]

    def get(self, key: str) -> str | None:
        for name, value in self.values:
            if name == key:
                return value
        return None


@dataclass(frozen=True)
class RelationMutation:
    operator: str
    target: str


@dataclass(frozen=True)
class RelationScenario:
    scenario_id: str
    name: str
    purpose: str
    relation_name: str
    world: MacroWorld
    mask: RelationMask
    mutations: tuple[RelationMutation, ...]
    expect_representable_before: bool
    expect_representable_after: bool
    expect_recoverable: bool
    expect_ambiguity: bool
    expect_mutation_accepted: bool
    epistemic_status: str
    ground_truth_present: bool
    observation_evidence_present: bool
    negative: bool


Rule = Callable[[tuple[RelationObservation, ...], RelationMask], bool]


@dataclass(frozen=True)
class RelationSpec:
    """Relation-specific evidence and interpretation. The evaluator only calls these rules."""

    name: str
    source_entity: str
    target_entity: str
    primitives: frozenset[str]
    evidence_rule: Rule
    interpretation_rule: Rule
    evidence_fields: tuple[tuple[str, str], ...] = ()


def _present(observations: tuple[RelationObservation, ...], key: str) -> bool:
    return any(observation.get(key) for observation in observations)


def requires(*pairs: tuple[str, str]) -> Rule:
    def rule(observations: tuple[RelationObservation, ...], mask: RelationMask) -> bool:
        for flag, key in pairs:
            if not getattr(mask, flag) or not _present(observations, key):
                return False
        return True

    return rule


def always(_observations: tuple[RelationObservation, ...], _mask: RelationMask) -> bool:
    return True


def never(_observations: tuple[RelationObservation, ...], _mask: RelationMask) -> bool:
    return False


def both_resources(observations: tuple[RelationObservation, ...], mask: RelationMask) -> bool:
    if not mask.expose_resource_id or not mask.expose_other_resource_id:
        return False
    return any(row.get("resource_id") and row.get("other_resource_id") for row in observations)


def two_systems(observations: tuple[RelationObservation, ...], mask: RelationMask) -> bool:
    if not mask.expose_system_id:
        return False
    return len({row.get("system_id") for row in observations if row.get("system_id")}) >= 2


def _flag(flag: str) -> Rule:
    def rule(_observations: tuple[RelationObservation, ...], mask: RelationMask) -> bool:
        return bool(getattr(mask, flag))

    return rule


def _spec(
    name: str,
    source: str,
    target: str,
    primitives: frozenset[str],
    evidence: Rule,
    interpretation: Rule,
    fields: tuple[tuple[str, str], ...],
) -> RelationSpec:
    return RelationSpec(name, source, target, primitives, evidence, interpretation, fields)


_ROLE_FIELDS = (("expose_resource_id", "resource_id"), ("expose_role", "role_id"))
_DEPARTMENT_FIELDS = (("expose_role", "role_id"), ("expose_department", "department_id"))
_ORGANIZATION_FIELDS = (("expose_department", "department_id"), ("expose_organization", "organization_id"))
_PAIR_FIELDS = (("expose_resource_id", "resource_id"), ("expose_other_resource_id", "other_resource_id"))
_TYPE_FIELDS = (("expose_relation_type", "relation_type"),)
_AUTHORITY_FIELDS = (("expose_authority", "authority_holder"), ("expose_holder_kind", "holder_kind"))
_INFORMATION_FIELDS = (("expose_system_id", "system_id"), ("expose_information", "information_id"))
_CAPACITY_FIELDS = (
    ("expose_capacity_pool", "capacity_pool_id"),
    ("expose_capacity_holder", "capacity_holder_id"),
    ("expose_capacity_holder", "capacity_holder_kind"),
)
_SYSTEM_FIELDS = (("expose_system_id", "system_id"),)

_ROLE = requires(*_ROLE_FIELDS)
_DEPARTMENT = requires(*_DEPARTMENT_FIELDS)
_ORGANIZATION = requires(*_ORGANIZATION_FIELDS)
_PAIR_TYPE = requires(*_TYPE_FIELDS)
_AUTHORITY = requires(*_AUTHORITY_FIELDS)
_INFORMATION = requires(*_INFORMATION_FIELDS)
_CAPACITY = requires(*_CAPACITY_FIELDS)
_HOLDER = _flag("expose_capacity_holder")

RELATION_SPECS: dict[str, RelationSpec] = {
    "resource_role": _spec("resource_role", "Resource", "Role", frozenset({"Role", "ResourceRoleAssociation"}), _ROLE, always, _ROLE_FIELDS),
    "role_department": _spec("role_department", "Role", "Department", frozenset({"Department", "RoleDepartmentAssociation"}), _DEPARTMENT, always, _DEPARTMENT_FIELDS),
    "department_organization": _spec(
        "department_organization",
        "Department",
        "Organization",
        frozenset({"Organization", "DepartmentOrganizationAssociation"}),
        _ORGANIZATION,
        always,
        _ORGANIZATION_FIELDS,
    ),
    "resource_collaborates": _spec("resource_collaborates", "Resource", "Resource", frozenset({"CollaboratesWith"}), both_resources, _PAIR_TYPE, _PAIR_FIELDS),
    "resource_substitutes": _spec("resource_substitutes", "Resource", "Resource", frozenset({"SubstitutesFor"}), both_resources, _PAIR_TYPE, _PAIR_FIELDS),
    "resource_depends": _spec("resource_depends", "Resource", "Resource", frozenset({"DependsOn"}), both_resources, _PAIR_TYPE, _PAIR_FIELDS),
    "role_authority": _spec("role_authority", "Role", "AuthorityRule", frozenset({"Authority", "RoleAuthorityAssociation"}), _AUTHORITY, _AUTHORITY, _AUTHORITY_FIELDS),
    "resource_authority": _spec(
        "resource_authority",
        "Resource",
        "AuthorityRule",
        frozenset({"Authority", "ResourceAuthorityAssociation"}),
        _AUTHORITY,
        _AUTHORITY,
        _AUTHORITY_FIELDS,
    ),
    "system_produces_information": _spec(
        "system_produces_information",
        "System",
        "InformationObject",
        frozenset({"InformationObject", "SystemInformationRelation"}),
        _INFORMATION,
        always,
        _INFORMATION_FIELDS,
    ),
    "information_consumed_by_system": _spec(
        "information_consumed_by_system",
        "InformationObject",
        "System",
        frozenset({"InformationObject", "InformationConsumption"}),
        _INFORMATION,
        always,
        _INFORMATION_FIELDS,
    ),
    "system_system": _spec("system_system", "System", "System", frozenset({"SystemSystemRelation"}), two_systems, never, _SYSTEM_FIELDS),
    "resource_capacity": _spec(
        "resource_capacity",
        "Resource",
        "CapacityPool",
        frozenset({"CapacityPool", "ResourceCapacityAssociation"}),
        _CAPACITY,
        _HOLDER,
        _CAPACITY_FIELDS,
    ),
    "role_capacity": _spec(
        "role_capacity",
        "Role",
        "CapacityPool",
        frozenset({"CapacityPool", "RoleCapacityAssociation"}),
        _CAPACITY,
        _HOLDER,
        _CAPACITY_FIELDS,
    ),
    "department_capacity": _spec(
        "department_capacity",
        "Department",
        "CapacityPool",
        frozenset({"CapacityPool", "DepartmentCapacityAssociation"}),
        _CAPACITY,
        _HOLDER,
        _CAPACITY_FIELDS,
    ),
}

RELATION_ENDS = {name: (spec.source_entity, spec.target_entity) for name, spec in RELATION_SPECS.items()}
REQUIREMENTS = {name: spec.primitives for name, spec in RELATION_SPECS.items()}
VOCABULARY = frozenset(primitive for spec in RELATION_SPECS.values() for primitive in spec.primitives)


def relation_spec(name: str, specs: Mapping[str, RelationSpec] | None = None) -> RelationSpec:
    registry = RELATION_SPECS if specs is None else specs
    return registry[name]

