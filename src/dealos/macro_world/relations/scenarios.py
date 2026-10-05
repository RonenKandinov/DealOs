"""One focused macro relation at a time. Expected flags are literals."""

from __future__ import annotations

from dealos.macro_world.relations.models import (
    FACT,
    HYPOTHESIS,
    MacroEvent,
    MacroRelation,
    MacroWorld,
    RelationMask,
    RelationMutation,
    RelationScenario,
    macro_r0,
)

PARTICIPATION = RelationMask()
DEPARTMENT_ONLY = RelationMask(expose_department=True, expose_resource_id=False, expose_activity=False)
SYSTEMS = RelationMask(expose_system_id=True, expose_resource_id=False, expose_activity=True)
PAIRED = RelationMask(expose_other_resource_id=True)


def all_relation_scenarios() -> tuple[RelationScenario, ...]:
    return (
        scenario_mr_a(),
        scenario_mr_b(),
        scenario_mr_c(),
        scenario_mr_d1(),
        scenario_mr_d2(),
        scenario_mr_d3(),
        scenario_mr_d0(),
        scenario_mr_e(),
        scenario_mr_f(),
        scenario_mr_g(),
        scenario_mr_h(),
        scenario_mr_i(),
        scenario_mr_j_resource(),
        scenario_mr_j_role(),
        scenario_mr_j_department(),
    )


def scenario_mr_a() -> RelationScenario:
    world = MacroWorld(
        relations=(
            _rel("a1", "resource_role", "R17", "role_legal", "belongs_to"),
            _rel("a2", "resource_role", "R22", "role_security", "belongs_to"),
        ),
        events=(
            _event(1, resource_id="R17", role_id="role_legal", activity="PacketCheck"),
            _event(2, resource_id="R22", role_id="role_security", activity="ScanCheck"),
        ),
    )
    return _scenario(
        "MR-A",
        "Resource to role",
        "R17 belongs to LegalReviewer and R22 belongs to SecurityReviewer. The mask hides the role.",
        "resource_role",
        world,
        PARTICIPATION,
        (RelationMutation("AddObject", "Role"), RelationMutation("AddRelation", "ResourceRoleAssociation")),
        False,
        True,
        False,
        False,
        True,
        FACT,
        True,
        False,
        False,
    )


def scenario_mr_b() -> RelationScenario:
    world = MacroWorld(
        relations=(
            _rel("b1", "role_department", "role_legal", "dept_legal", "belongs_to"),
            _rel("b2", "role_department", "role_security", "dept_security", "belongs_to"),
        ),
        events=(
            _event(1, resource_id="R17", role_id="role_legal", department_id="dept_legal", activity="PacketCheck"),
            _event(2, resource_id="R22", role_id="role_security", department_id="dept_security", activity="ScanCheck"),
        ),
    )
    return _scenario(
        "MR-B",
        "Role to department",
        "LegalReviewer belongs to Legal and SecurityReviewer belongs to Security. Role and department stay hidden.",
        "role_department",
        world,
        PARTICIPATION,
        (RelationMutation("AddObject", "Department"), RelationMutation("AddRelation", "RoleDepartmentAssociation")),
        False,
        True,
        False,
        False,
        True,
        FACT,
        True,
        False,
        False,
    )


def scenario_mr_c() -> RelationScenario:
    world = MacroWorld(
        relations=(
            _rel("c1", "department_organization", "dept_legal", "OrgA", "belongs_to"),
            _rel("c2", "department_organization", "dept_security", "OrgA", "belongs_to"),
        ),
        events=(
            _event(1, department_id="dept_legal", organization_id="OrgA", activity="PacketCheck"),
            _event(2, department_id="dept_security", organization_id="OrgA", activity="ScanCheck"),
        ),
    )
    return _scenario(
        "MR-C",
        "Department to organization",
        "Legal and Security both belong to OrgA. Department ids are exposed and the organization id is hidden.",
        "department_organization",
        world,
        DEPARTMENT_ONLY,
        (
            RelationMutation("AddObject", "Organization"),
            RelationMutation("AddRelation", "DepartmentOrganizationAssociation"),
        ),
        False,
        True,
        False,
        False,
        True,
        FACT,
        True,
        False,
        False,
    )


def scenario_mr_d1() -> RelationScenario:
    return _resource_pair("MR-D1", "collaborates_with", "resource_collaborates", "CollaboratesWith")


def scenario_mr_d2() -> RelationScenario:
    return _resource_pair("MR-D2", "substitutes_for", "resource_substitutes", "SubstitutesFor")


def scenario_mr_d3() -> RelationScenario:
    return _resource_pair("MR-D3", "depends_on", "resource_depends", "DependsOn")


def scenario_mr_d0() -> RelationScenario:
    world = MacroWorld(
        relations=(),
        events=(_event(1, resource_id="R17", other_resource_id="R31", activity="JointStep"),),
    )
    return _scenario(
        "MR-D0",
        "Resource co-presence without a relation",
        "R17 and R31 appear together. Ground truth has no resource-to-resource relation.",
        "resource_collaborates",
        world,
        PAIRED,
        (RelationMutation("AddRelation", "CollaboratesWith"),),
        False,
        True,
        False,
        True,
        False,
        HYPOTHESIS,
        False,
        True,
        True,
    )


def scenario_mr_e() -> RelationScenario:
    world = MacroWorld(
        relations=(_rel("e1", "role_authority", "role_finance", "auth_approve", "can_authorize"),),
        events=(
            _event(1, resource_id="Fin_R1", activity="ApproveDeal", authority_holder="role_finance", holder_kind="role"),
            _event(2, resource_id="Clerk_R2", activity="ApproveDeal"),
        ),
    )
    return _scenario(
        "MR-E",
        "Role authority",
        "FinanceApprover can authorize ApproveDeal. Clerk_R2 appears on the same action and has no authority rule.",
        "role_authority",
        world,
        PARTICIPATION,
        (RelationMutation("AddObject", "Authority"), RelationMutation("AddRelation", "RoleAuthorityAssociation")),
        False,
        True,
        False,
        True,
        False,
        HYPOTHESIS,
        True,
        False,
        False,
    )


def scenario_mr_f() -> RelationScenario:
    world = MacroWorld(
        relations=(_rel("f1", "resource_authority", "Fin_R1", "auth_approve", "can_authorize"),),
        events=(
            _event(1, resource_id="Fin_R1", activity="ApproveDeal", authority_holder="Fin_R1", holder_kind="resource"),
            _event(2, resource_id="Clerk_R2", activity="ApproveDeal"),
        ),
    )
    return _scenario(
        "MR-F",
        "Resource authority",
        "The authority rule is attached to Fin_R1 itself. The event stream matches the role-authority stream.",
        "resource_authority",
        world,
        PARTICIPATION,
        (RelationMutation("AddObject", "Authority"), RelationMutation("AddRelation", "ResourceAuthorityAssociation")),
        False,
        True,
        False,
        True,
        False,
        HYPOTHESIS,
        True,
        False,
        False,
    )


def scenario_mr_g() -> RelationScenario:
    world = MacroWorld(
        relations=(
            _rel("g1", "system_produces_information", "sys_crm", "info_profile", "produces"),
            _rel("g2", "system_produces_information", "sys_risk", "info_risk", "produces"),
        ),
        events=(
            _event(1, system_id="sys_crm", information_id="info_profile", activity="EmitProfile"),
            _event(2, system_id="sys_risk", information_id="info_risk", activity="ScoreRisk"),
        ),
    )
    return _scenario(
        "MR-G",
        "System produces information",
        "CRM produces CustomerProfile and RiskEngine produces RiskAssessment. The information id is hidden.",
        "system_produces_information",
        world,
        SYSTEMS,
        (
            RelationMutation("AddObject", "InformationObject"),
            RelationMutation("AddRelation", "SystemInformationRelation"),
        ),
        False,
        True,
        False,
        False,
        True,
        FACT,
        True,
        False,
        False,
    )


def scenario_mr_h() -> RelationScenario:
    world = MacroWorld(
        relations=(
            _rel("h1", "information_consumed_by_system", "info_profile", "sys_risk", "consumed_by"),
            _rel("h2", "information_consumed_by_system", "info_risk", "sys_approval", "consumed_by"),
        ),
        events=(
            _event(1, system_id="sys_risk", information_id="info_profile", activity="ScoreRisk"),
            _event(2, system_id="sys_approval", information_id="info_risk", activity="Gate"),
        ),
    )
    return _scenario(
        "MR-H",
        "Information consumed by system",
        "CustomerProfile is consumed by RiskEngine and RiskAssessment by ApprovalSystem. The link is hidden.",
        "information_consumed_by_system",
        world,
        SYSTEMS,
        (
            RelationMutation("AddObject", "InformationObject"),
            RelationMutation("AddRelation", "InformationConsumption"),
        ),
        False,
        True,
        False,
        False,
        True,
        FACT,
        True,
        False,
        False,
    )


def scenario_mr_i() -> RelationScenario:
    world = MacroWorld(
        relations=(),
        events=(
            _event(1, system_id="sys_crm", activity="EmitProfile"),
            _event(2, system_id="sys_risk", activity="ScoreRisk"),
            _event(3, system_id="sys_approval", activity="Gate"),
        ),
    )
    return _scenario(
        "MR-I",
        "System succession",
        "CRM, RiskEngine, and ApprovalSystem occur in order. Ground truth stores no system-to-system relation.",
        "system_system",
        world,
        SYSTEMS,
        (RelationMutation("AddRelation", "SystemSystemRelation"),),
        False,
        True,
        False,
        True,
        False,
        HYPOTHESIS,
        False,
        True,
        True,
    )


def scenario_mr_j_resource() -> RelationScenario:
    return _capacity(
        "MR-J1",
        "Resource capacity",
        "resource_capacity",
        "ResourceCapacityAssociation",
        True,
        True,
        False,
        HYPOTHESIS,
        False,
    )


def scenario_mr_j_role() -> RelationScenario:
    return _capacity(
        "MR-J2",
        "Role capacity",
        "role_capacity",
        "RoleCapacityAssociation",
        True,
        True,
        False,
        HYPOTHESIS,
        False,
    )


def scenario_mr_j_department() -> RelationScenario:
    return _capacity(
        "MR-J3",
        "Department capacity",
        "department_capacity",
        "DepartmentCapacityAssociation",
        False,
        True,
        True,
        HYPOTHESIS,
        False,
    )


def _resource_pair(scenario_id: str, semantic: str, relation_name: str, target: str) -> RelationScenario:
    world = MacroWorld(
        relations=(_rel("d1", relation_name, "R17", "R22", semantic),),
        events=(_event(1, resource_id="R17", other_resource_id="R22", activity="JointStep", relation_type=semantic),),
    )
    return _scenario(
        scenario_id,
        f"Resource pair {semantic}",
        f"Ground truth says R17 {semantic} R22. The event shows both ids and hides the type.",
        relation_name,
        world,
        PAIRED,
        (RelationMutation("AddRelation", target),),
        False,
        True,
        False,
        True,
        False,
        HYPOTHESIS,
        True,
        True,
        False,
    )


def _capacity(
    scenario_id: str,
    name: str,
    relation_name: str,
    target: str,
    present: bool,
    ambiguity: bool,
    negative: bool,
    status: str,
    accepted: bool,
) -> RelationScenario:
    relations = [
        _rel("j1", "resource_capacity", "R17", "pool_legal", "held_by"),
        _rel("j2", "resource_capacity", "R22", "pool_legal", "held_by"),
        _rel("j3", "role_capacity", "role_legal", "pool_legal", "held_by"),
    ]
    if not present and relation_name != "department_capacity":
        relations = [relation for relation in relations if relation.name == relation_name]
    world = MacroWorld(
        relations=tuple(relations),
        events=(
            _event(
                1,
                resource_id="R17",
                capacity_pool_id="pool_legal",
                capacity_holder_id="R17",
                capacity_holder_kind="resource",
                activity="Counsel",
            ),
            _event(
                2,
                resource_id="R22",
                capacity_pool_id="pool_legal",
                capacity_holder_id="role_legal",
                capacity_holder_kind="role",
                activity="Counsel",
            ),
        ),
    )
    return _scenario(
        scenario_id,
        name,
        "R17 and R22 share CapacityPool_Legal, and LegalRole is also attached to that pool. Department capacity is absent.",
        relation_name,
        world,
        PARTICIPATION,
        (RelationMutation("AddObject", "CapacityPool"), RelationMutation("AddRelation", target)),
        False,
        True,
        False,
        ambiguity,
        accepted,
        status,
        present,
        False,
        negative,
    )


def _scenario(
    scenario_id: str,
    name: str,
    purpose: str,
    relation_name: str,
    world: MacroWorld,
    mask: RelationMask,
    mutations: tuple[RelationMutation, ...],
    before: bool,
    after: bool,
    recovered: bool,
    ambiguity: bool,
    accepted: bool,
    status: str,
    present: bool,
    evidence: bool,
    negative: bool,
) -> RelationScenario:
    return RelationScenario(
        scenario_id,
        name,
        purpose,
        relation_name,
        world,
        mask,
        mutations,
        before,
        after,
        recovered,
        ambiguity,
        accepted,
        status,
        present,
        evidence,
        negative,
    )


def _rel(relation_id: str, name: str, source_id: str, target_id: str, semantic: str) -> MacroRelation:
    return MacroRelation(relation_id, name, source_id, target_id, semantic)


def _event(order: int, **kwargs: str) -> MacroEvent:
    return MacroEvent(f"e{order:04d}", order, **kwargs)


def initial_representation():
    return macro_r0()
