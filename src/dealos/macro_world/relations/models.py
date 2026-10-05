"""Macro-to-macro relation records. These are not a bridge into the micro graph."""

from __future__ import annotations

from dataclasses import dataclass

from dealos.macro_world.models import Representation

MACRO_R0 = frozenset({"PersistentResourceIdentifier", "ResourceOccurrenceAssociation"})
OPERATORS = frozenset({"AddObject", "AddRelation", "AddState", "AddAttribute"})
BRIDGE = frozenset({"TaskOccurrence", "TaskType", "Deal", "Task", "Allocation", "ResourceOccurrenceAssociation"})
FACT = "FACT"
INFERENCE = "INFERENCE"
HYPOTHESIS = "HYPOTHESIS"

RELATION_ENDS = {
    "resource_role": ("Resource", "Role"),
    "role_department": ("Role", "Department"),
    "department_organization": ("Department", "Organization"),
    "resource_collaborates": ("Resource", "Resource"),
    "resource_substitutes": ("Resource", "Resource"),
    "resource_depends": ("Resource", "Resource"),
    "role_authority": ("Role", "AuthorityRule"),
    "resource_authority": ("Resource", "AuthorityRule"),
    "system_produces_information": ("System", "InformationObject"),
    "information_consumed_by_system": ("InformationObject", "System"),
    "system_system": ("System", "System"),
    "resource_capacity": ("Resource", "CapacityPool"),
    "role_capacity": ("Role", "CapacityPool"),
    "department_capacity": ("Department", "CapacityPool"),
}

REQUIREMENTS = {
    "resource_role": frozenset({"Role", "ResourceRoleAssociation"}),
    "role_department": frozenset({"Department", "RoleDepartmentAssociation"}),
    "department_organization": frozenset({"Organization", "DepartmentOrganizationAssociation"}),
    "resource_collaborates": frozenset({"CollaboratesWith"}),
    "resource_substitutes": frozenset({"SubstitutesFor"}),
    "resource_depends": frozenset({"DependsOn"}),
    "role_authority": frozenset({"Authority", "RoleAuthorityAssociation"}),
    "resource_authority": frozenset({"Authority", "ResourceAuthorityAssociation"}),
    "system_produces_information": frozenset({"InformationObject", "SystemInformationRelation"}),
    "information_consumed_by_system": frozenset({"InformationObject", "InformationConsumption"}),
    "system_system": frozenset({"SystemSystemRelation"}),
    "resource_capacity": frozenset({"CapacityPool", "ResourceCapacityAssociation"}),
    "role_capacity": frozenset({"CapacityPool", "RoleCapacityAssociation"}),
    "department_capacity": frozenset({"CapacityPool", "DepartmentCapacityAssociation"}),
}

VOCABULARY = frozenset(name for names in REQUIREMENTS.values() for name in names)
AMBIGUOUS = frozenset(
    {
        "resource_collaborates",
        "resource_substitutes",
        "resource_depends",
        "role_authority",
        "resource_authority",
        "system_system",
    }
)
TYPED_RESOURCE = frozenset({"resource_collaborates", "resource_substitutes", "resource_depends"})


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
