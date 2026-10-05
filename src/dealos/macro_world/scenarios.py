"""Scenario specifications. Expected booleans are literals, not calls into the query layer."""

from __future__ import annotations

from dataclasses import dataclass

from dealos.macro_world.generator import (
    world_ambiguous,
    world_authority,
    world_departments,
    world_information,
    world_resource_identity,
    world_resource_role,
    world_shared_capacity,
)
from dealos.macro_world.models import (
    FACT,
    HYPOTHESIS,
    GroundTruth,
    Mismatch,
    Mutation,
    ObservationMask,
    Representation,
    micro_representation,
    r0_representation,
)

PARTICIPATION = ObservationMask()
SYSTEM_EVENTS = ObservationMask(expose_system_id=True, expose_resource_id=False)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    name: str
    purpose: str
    ground_truth: GroundTruth
    mask: ObservationMask
    initial: Representation
    missing_primitive: str
    mismatch: Mismatch
    mutations: tuple[Mutation, ...]
    capability: str
    expect_representable_before: bool
    expect_representable_after: bool
    expect_recoverable: bool
    epistemic_status: str
    accept_mutation: bool
    decision: str
    secondary_capability: str = ""
    expect_secondary_representable: bool = False
    expect_secondary_recoverable: bool = False


def all_scenarios() -> tuple[Scenario, ...]:
    return (
        scenario_a(),
        scenario_b(),
        scenario_c(),
        scenario_d(),
        scenario_e(),
        scenario_f(),
        scenario_g(),
    )


def scenario_by_id(scenario_id: str) -> Scenario:
    for scenario in all_scenarios():
        if scenario.scenario_id == scenario_id:
            return scenario
    raise KeyError(scenario_id)


def scenario_a() -> Scenario:
    mutations = (
        Mutation("AddObject", "PersistentResourceIdentifier"),
        Mutation("AddRelation", "ResourceOccurrenceAssociation"),
    )
    return Scenario(
        "A",
        "Resource identity",
        "The same resource id appears in more than one deal, and the event stream shows that id.",
        world_resource_identity(),
        PARTICIPATION,
        micro_representation(),
        "PersistentResourceIdentifier, ResourceOccurrenceAssociation",
        Mismatch(
            "M001",
            "The same resource_id appears across multiple occurrences.",
            "resource-occurrence identity",
            FACT,
            ("R17",),
            ("AddObject PersistentResourceIdentifier", "AddRelation ResourceOccurrenceAssociation"),
        ),
        mutations,
        "resource_occurrence_identity",
        False,
        True,
        True,
        FACT,
        True,
        "identifier and association are representable and recoverable",
    )


def scenario_b() -> Scenario:
    mutations = (Mutation("AddObject", "Role"), Mutation("AddRelation", "ResourceRoleAssociation"))
    return Scenario(
        "B",
        "Resource to role",
        "Ground truth links R17 to LegalReviewer. The activity name is PacketCheck, and the mask hides the role.",
        world_resource_role(),
        PARTICIPATION,
        r0_representation(),
        "Role, ResourceRoleAssociation",
        Mismatch(
            "M002",
            "A persistent resource id participates. The role is not in the event stream.",
            "role representation",
            FACT,
            ("R17",),
            ("AddObject Role", "AddRelation ResourceRoleAssociation"),
        ),
        mutations,
        "role",
        False,
        True,
        False,
        FACT,
        True,
        "role is representable only after the mutation and is not recoverable",
    )


def scenario_c() -> Scenario:
    mutations = (Mutation("AddObject", "Department"), Mutation("AddRelation", "RoleDepartmentAssociation"))
    return Scenario(
        "C",
        "Department structure",
        "Ground truth groups LegalReviewer under Legal and SecurityReviewer under Security. The mask hides the department.",
        world_departments(),
        PARTICIPATION,
        r0_representation(),
        "Department, RoleDepartmentAssociation",
        Mismatch(
            "M003",
            "Resource ids and activities are exposed. Department membership is not.",
            "department representation",
            FACT,
            ("R17", "R22"),
            ("AddObject Department", "AddRelation RoleDepartmentAssociation"),
        ),
        mutations,
        "department",
        False,
        True,
        False,
        FACT,
        True,
        "department is representable only after the mutation and is not recoverable",
    )


def scenario_d() -> Scenario:
    return Scenario(
        "D",
        "Authority",
        "FinanceApprover is the only holder of ApproveDeal. Clerk_R2 can appear on that activity and has no authority rule.",
        world_authority(),
        PARTICIPATION,
        r0_representation(),
        "Authority",
        Mismatch(
            "M004",
            "Two resources appear on ApproveDeal. The authority rule is not in the event stream.",
            "authority representation",
            FACT,
            ("Fin_R1", "Clerk_R2"),
            ("AddObject Authority",),
        ),
        (Mutation("AddObject", "Authority"),),
        "authority",
        False,
        True,
        False,
        FACT,
        True,
        "authority is representable only after the mutation and is not recoverable",
    )


def scenario_e() -> Scenario:
    mutations = (Mutation("AddObject", "InformationObject"), Mutation("AddRelation", "InformationDependency"))
    return Scenario(
        "E",
        "Information dependency",
        "CRM produces CustomerProfile, RiskEngine consumes it and produces RiskAssessment, and ApprovalSystem consumes RiskAssessment.",
        world_information(),
        SYSTEM_EVENTS,
        r0_representation(),
        "InformationObject, InformationDependency",
        Mismatch(
            "M005",
            "System ids are exposed. The produces and consumes links are not.",
            "information dependency",
            FACT,
            ("sys_crm", "sys_risk", "sys_approval"),
            ("AddObject InformationObject", "AddRelation InformationDependency"),
        ),
        mutations,
        "information_dependency",
        False,
        True,
        False,
        FACT,
        True,
        "information dependency is representable only after the mutation and is not recoverable",
    )


def scenario_f() -> Scenario:
    return Scenario(
        "F",
        "Shared resource",
        "Legal_R1 participates in Deal_1, Deal_2, and Deal_3. One capacity pool has size 1. The pool size is hidden.",
        world_shared_capacity(),
        PARTICIPATION,
        r0_representation(),
        "none",
        Mismatch(
            "M006",
            "One resource id appears in three deals. The capacity number is not in the event stream.",
            "hidden capacity value",
            FACT,
            ("Legal_R1",),
            (),
        ),
        (),
        "shared_identity",
        True,
        True,
        True,
        FACT,
        False,
        "shared identity is already representable and the capacity value is not recoverable",
        secondary_capability="capacity_pool",
        expect_secondary_representable=True,
        expect_secondary_recoverable=False,
    )


def scenario_g() -> Scenario:
    return Scenario(
        "G",
        "Multiple interpretations",
        "R17 appears on LegalReview, ContractReview, and Approval. Ground truth does not choose a role, a delegation, or a shared-resource reading.",
        world_ambiguous(),
        PARTICIPATION,
        r0_representation(),
        "none",
        Mismatch(
            "M007",
            "One resource id appears on three activity names. No role or authority relation is in the ground truth.",
            "unresolved interpretation",
            HYPOTHESIS,
            ("R17",),
            (),
        ),
        (),
        "ambiguous_interpretation",
        False,
        False,
        False,
        HYPOTHESIS,
        False,
        "HYPOTHESIS unresolved",
    )
