"""Deterministic ground-truth worlds. The seed does not change which objects exist."""

from __future__ import annotations

from dealos.macro_world.models import (
    AuthorityRule,
    CapacityPool,
    Deal,
    Department,
    GroundTruth,
    InformationObject,
    Organization,
    Resource,
    Role,
    System,
    TaskOccurrence,
    TaskType,
    Trace,
)

ORG = Organization("org")


def world_resource_identity() -> GroundTruth:
    deals = (Deal("d1"), Deal("d2"), Deal("d3"))
    task = TaskType("review", "Review")
    occurrences = tuple(_occurrence(deal.deal_id, task.task_id) for deal in deals)
    resource = Resource("R17", "", "org_resource")
    return GroundTruth(
        organization=ORG,
        resources=(resource,),
        deals=deals,
        task_types=(task,),
        occurrences=occurrences,
        performs=tuple((resource.resource_id, row.occurrence_id) for row in occurrences),
        allocated_to=tuple((resource.resource_id, row.occurrence_id) for row in occurrences),
        traces=tuple(
            _trace(index, row.deal_id, task.name, resource.resource_id, row.lifecycle)
            for index, row in enumerate(occurrences, start=1)
        ),
    )


def world_resource_role() -> GroundTruth:
    department = Department("dept_legal", ORG.organization_id, "Legal")
    role = Role("role_legal_reviewer", department.department_id, "LegalReviewer")
    resource = Resource("R17", role.role_id, "org_resource")
    task = TaskType("packet_check", "PacketCheck")
    deals = (Deal("d1"), Deal("d2"))
    occurrences = tuple(_occurrence(deal.deal_id, task.task_id) for deal in deals)
    return GroundTruth(
        organization=ORG,
        departments=(department,),
        roles=(role,),
        resources=(resource,),
        deals=deals,
        task_types=(task,),
        occurrences=occurrences,
        belongs_resource_role=((resource.resource_id, role.role_id),),
        belongs_role_department=((role.role_id, department.department_id),),
        performs=tuple((resource.resource_id, row.occurrence_id) for row in occurrences),
        allocated_to=tuple((resource.resource_id, row.occurrence_id) for row in occurrences),
        traces=tuple(
            _trace(
                index,
                row.deal_id,
                task.name,
                resource.resource_id,
                row.lifecycle,
                role_id=role.role_id,
                department_id=department.department_id,
            )
            for index, row in enumerate(occurrences, start=1)
        ),
    )


def world_departments() -> GroundTruth:
    legal = Department("dept_legal", ORG.organization_id, "Legal")
    security = Department("dept_security", ORG.organization_id, "Security")
    legal_role = Role("role_legal_reviewer", legal.department_id, "LegalReviewer")
    security_role = Role("role_security_reviewer", security.department_id, "SecurityReviewer")
    r17 = Resource("R17", legal_role.role_id, "org_resource")
    r22 = Resource("R22", security_role.role_id, "org_resource")
    legal_task = TaskType("legal_packet", "LegalPacket")
    security_task = TaskType("security_packet", "SecurityPacket")
    first = _occurrence("d1", legal_task.task_id)
    second = _occurrence("d2", security_task.task_id)
    return GroundTruth(
        organization=ORG,
        departments=(legal, security),
        roles=(legal_role, security_role),
        resources=(r17, r22),
        deals=(Deal("d1"), Deal("d2")),
        task_types=(legal_task, security_task),
        occurrences=(first, second),
        belongs_resource_role=((r17.resource_id, legal_role.role_id), (r22.resource_id, security_role.role_id)),
        belongs_role_department=(
            (legal_role.role_id, legal.department_id),
            (security_role.role_id, security.department_id),
        ),
        performs=((r17.resource_id, first.occurrence_id), (r22.resource_id, second.occurrence_id)),
        allocated_to=((r17.resource_id, first.occurrence_id), (r22.resource_id, second.occurrence_id)),
        traces=(
            _trace(1, "d1", legal_task.name, r17.resource_id, first.lifecycle, role_id=legal_role.role_id, department_id=legal.department_id),
            _trace(2, "d2", security_task.name, r22.resource_id, second.lifecycle, role_id=security_role.role_id, department_id=security.department_id),
        ),
    )


def world_authority() -> GroundTruth:
    department = Department("dept_finance", ORG.organization_id, "Finance")
    approver = Role("role_finance_approver", department.department_id, "FinanceApprover")
    clerk = Role("role_clerk", department.department_id, "Clerk")
    fin = Resource("Fin_R1", approver.role_id, "org_resource")
    other = Resource("Clerk_R2", clerk.role_id, "org_resource")
    task = TaskType("approve_deal", "ApproveDeal")
    approved = _occurrence("d1", task.task_id, number=1)
    recorded = _occurrence("d1", task.task_id, number=2)
    rule = AuthorityRule("auth_approve", approver.role_id, "role", task.name, "deal")
    return GroundTruth(
        organization=ORG,
        departments=(department,),
        roles=(approver, clerk),
        resources=(fin, other),
        deals=(Deal("d1"),),
        task_types=(task,),
        occurrences=(approved, recorded),
        authority_rules=(rule,),
        belongs_resource_role=((fin.resource_id, approver.role_id), (other.resource_id, clerk.role_id)),
        belongs_role_department=((approver.role_id, department.department_id), (clerk.role_id, department.department_id)),
        performs=((fin.resource_id, approved.occurrence_id), (other.resource_id, recorded.occurrence_id)),
        allocated_to=((fin.resource_id, approved.occurrence_id), (other.resource_id, recorded.occurrence_id)),
        authorizes=((approver.role_id, task.name),),
        traces=(
            _trace(1, "d1", task.name, fin.resource_id, approved.lifecycle, role_id=approver.role_id, authority=task.name),
            _trace(2, "d1", task.name, other.resource_id, recorded.lifecycle, role_id=clerk.role_id),
        ),
    )


def world_information() -> GroundTruth:
    crm = System("sys_crm", "CRM")
    risk = System("sys_risk", "RiskEngine")
    approval = System("sys_approval", "ApprovalSystem")
    profile = InformationObject("info_profile", "CustomerProfile", crm.system_id, (risk.system_id,))
    assessment = InformationObject("info_risk", "RiskAssessment", risk.system_id, (approval.system_id,))
    emit = TaskType("emit_profile", "EmitProfile")
    score = TaskType("score_risk", "ScoreRisk")
    gate = TaskType("gate", "Gate")
    occurrences = (
        _occurrence("d1", emit.task_id, number=1),
        _occurrence("d1", score.task_id, number=1),
        _occurrence("d1", gate.task_id, number=1),
    )
    return GroundTruth(
        organization=ORG,
        systems=(crm, risk, approval),
        deals=(Deal("d1"),),
        task_types=(emit, score, gate),
        occurrences=occurrences,
        information=(profile, assessment),
        produces=((crm.system_id, profile.information_id), (risk.system_id, assessment.information_id)),
        consumes=((risk.system_id, profile.information_id), (approval.system_id, assessment.information_id)),
        requires=((occurrences[1].occurrence_id, profile.information_id), (occurrences[2].occurrence_id, assessment.information_id)),
        traces=(
            _trace(1, "d1", emit.name, "", occurrences[0].lifecycle, system_id=crm.system_id, information_id=profile.information_id),
            _trace(2, "d1", score.name, "", occurrences[1].lifecycle, system_id=risk.system_id, information_id=profile.information_id),
            _trace(3, "d1", gate.name, "", occurrences[2].lifecycle, system_id=approval.system_id, information_id=assessment.information_id),
        ),
    )


def world_shared_capacity() -> GroundTruth:
    resource = Resource("Legal_R1", "", "org_resource")
    task = TaskType("counsel", "Counsel")
    deals = (Deal("Deal_1"), Deal("Deal_2"), Deal("Deal_3"))
    occurrences = tuple(_occurrence(deal.deal_id, task.task_id) for deal in deals)
    pool = CapacityPool("pool_legal", resource.resource_id, "", 1.0)
    return GroundTruth(
        organization=ORG,
        resources=(resource,),
        deals=deals,
        task_types=(task,),
        occurrences=occurrences,
        capacity_pools=(pool,),
        performs=tuple((resource.resource_id, row.occurrence_id) for row in occurrences),
        allocated_to=tuple((resource.resource_id, row.occurrence_id) for row in occurrences),
        traces=tuple(
            _trace(index, row.deal_id, task.name, resource.resource_id, row.lifecycle, capacity="1")
            for index, row in enumerate(occurrences, start=1)
        ),
    )


def world_ambiguous() -> GroundTruth:
    resource = Resource("R17", "", "org_resource")
    names = (("legal_review", "LegalReview"), ("contract_review", "ContractReview"), ("approval", "Approval"))
    tasks = tuple(TaskType(task_id, name) for task_id, name in names)
    occurrences = tuple(_occurrence("d1", task.task_id) for task in tasks)
    return GroundTruth(
        organization=ORG,
        resources=(resource,),
        deals=(Deal("d1"),),
        task_types=tasks,
        occurrences=occurrences,
        performs=tuple((resource.resource_id, row.occurrence_id) for row in occurrences),
        allocated_to=tuple((resource.resource_id, row.occurrence_id) for row in occurrences),
        traces=tuple(
            _trace(index, "d1", task.name, resource.resource_id, row.lifecycle)
            for index, (task, row) in enumerate(zip(tasks, occurrences, strict=True), start=1)
        ),
    )


def reference_world() -> GroundTruth:
    department = Department("dept_legal", ORG.organization_id, "Legal")
    role = Role("role_legal_reviewer", department.department_id, "LegalReviewer")
    resource = Resource("R17", role.role_id, "org_resource")
    producer = System("sys_crm", "CRM")
    consumer = System("sys_risk", "RiskEngine")
    info = InformationObject("info_profile", "CustomerProfile", producer.system_id, (consumer.system_id,))
    first = TaskType("intake", "Intake")
    second = TaskType("review", "Review")
    occurrence = _occurrence("d1", second.task_id)
    rule = AuthorityRule("auth_review", role.role_id, "role", second.name, "deal")
    pool = CapacityPool("pool_r17", resource.resource_id, "", 1.0)
    return GroundTruth(
        organization=ORG,
        departments=(department,),
        roles=(role,),
        resources=(resource,),
        systems=(producer, consumer),
        deals=(Deal("d1"),),
        task_types=(first, second),
        occurrences=(occurrence,),
        information=(info,),
        authority_rules=(rule,),
        capacity_pools=(pool,),
        belongs_resource_role=((resource.resource_id, role.role_id),),
        belongs_role_department=((role.role_id, department.department_id),),
        performs=((resource.resource_id, occurrence.occurrence_id),),
        requires=((occurrence.occurrence_id, info.information_id),),
        produces=((producer.system_id, info.information_id),),
        consumes=((consumer.system_id, info.information_id),),
        authorizes=((role.role_id, second.name),),
        allocated_to=((resource.resource_id, occurrence.occurrence_id),),
        depends_on=((first.task_id, second.task_id),),
        traces=(_trace(1, "d1", second.name, resource.resource_id, occurrence.lifecycle, system_id=producer.system_id, information_id=info.information_id, role_id=role.role_id, department_id=department.department_id, authority=second.name, capacity="1"),),
    )


def _occurrence(deal_id: str, task_id: str, number: int = 1) -> TaskOccurrence:
    return TaskOccurrence(f"{deal_id}:{task_id}#{number}", deal_id, task_id, "active", 0.0)


def _trace(
    index: int,
    deal_id: str,
    activity: str,
    resource_id: str,
    lifecycle: str,
    system_id: str = "",
    information_id: str = "",
    role_id: str = "",
    department_id: str = "",
    authority: str = "",
    capacity: str = "",
) -> Trace:
    return Trace(
        f"e{index:04d}",
        deal_id,
        activity,
        lifecycle,
        resource_id,
        system_id,
        information_id,
        role_id,
        department_id,
        authority,
        capacity,
    )
