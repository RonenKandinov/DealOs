"""Deterministic checks for organizational state and the macro gate."""

from dataclasses import fields

import pytest

from dealos.domain.models import Task
from dealos.org.operating.bridge import (
    CAN_PROGRESS,
    CAPACITY_UNAVAILABLE,
    EXTERNAL_INFORMATION_UNAVAILABLE,
    INFORMATION_UNAVAILABLE,
    VETO,
    diagnose,
)
from dealos.org.operating.entities import (
    AuthorityGrant,
    BusinessUnit,
    Capability,
    CapacityPool,
    Decision,
    Department,
    EscalationRule,
    ExternalRelation,
    InformationObject,
    Organization,
    Person,
    Resource,
    Role,
    SLA,
    System,
    TaskConstraint,
    Team,
)
from dealos.org.operating.state import OrgState, integrity_errors
from dealos.org.operating.transition import (
    Allocate,
    Approve,
    AssignCapability,
    AssignRole,
    Delegate,
    GrantDecisionRight,
    IssueVeto,
    Participate,
    ProduceInformation,
    ReceiveExternalInformation,
    Release,
    Tick,
    TransitionError,
    apply,
)
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1


def _base() -> OrgState:
    state = OrgState()
    state.organizations["seller"] = Organization("seller")
    state.organizations["buyer"] = Organization("buyer", external=True)
    state.departments["legal"] = Department("legal", "seller")
    state.roles["approver"] = Role("approver", "legal")
    state.roles["clerk"] = Role("clerk", "legal")
    state.resources["R1"] = Resource("R1")
    state.capacity["pool"] = CapacityPool("pool", 1.0, 1.0)
    state.decisions["approve_deal"] = Decision("approve_deal", "ApproveDeal", "open")
    state.authority["grant"] = AuthorityGrant("grant", "approver", "role", "approve_deal")
    state.information["profile"] = InformationObject("profile", False)
    state.systems["crm"] = System("crm", "seller")
    state.external_relations["buyer_profile"] = ExternalRelation("buyer_profile", "buyer", "seller", "profile")
    state.escalation_rules["no_holder"] = EscalationRule("no_holder", "clerk", "approver", "authority_unavailable")
    state.escalation_rules["sla"] = EscalationRule("sla", "clerk", "approver", "sla_breached")
    state.slas["clock"] = SLA("clock", "approve_deal", 5, False)
    assert integrity_errors(state) == ()
    return state


def test_ready_task_with_capacity_can_progress_and_exhausted_capacity_cannot() -> None:
    state = _base()
    constraint = TaskConstraint("legal_review", capacity_pool_id="pool", ready=True)
    assert diagnose(state, constraint).reason == CAN_PROGRESS
    held = apply(state, Allocate("pool", 1.0, "R1"))
    assert diagnose(held, constraint).reason == CAPACITY_UNAVAILABLE
    released = apply(held, Release("pool", 1.0))
    assert diagnose(released, constraint).reason == CAN_PROGRESS


def test_information_blocks_until_it_is_produced() -> None:
    state = _base()
    constraint = TaskConstraint("review", information_id="profile", ready=True)
    assert diagnose(state, constraint).reason == INFORMATION_UNAVAILABLE
    produced = apply(state, ProduceInformation("profile", "crm"))
    assert diagnose(produced, constraint).reason == CAN_PROGRESS


def test_authorized_holder_can_approve_and_a_missing_holder_escalates() -> None:
    state = _base()
    assert apply(state, Approve("approve_deal", "approver")).decisions["approve_deal"].status == "approved"
    missing = OrgState()
    missing.decisions["approve_deal"] = Decision("approve_deal", "ApproveDeal", "open")
    missing.escalation_rules["no_holder"] = EscalationRule("no_holder", "clerk", "approver", "authority_unavailable")
    escalated = apply(missing, Approve("approve_deal", "clerk"))
    assert escalated.decisions["approve_deal"].status == "escalated"
    assert "esc:approve_deal" in escalated.escalations


def test_delegation_changes_who_can_act_and_veto_blocks_the_holder() -> None:
    state = _base()
    delegated = apply(state, Delegate("d1", "approver", "clerk", "approve_deal"))
    assert apply(delegated, Approve("approve_deal", "clerk")).decisions["approve_deal"].status == "approved"
    vetoed = apply(state, IssueVeto("v1", "buyer", "approve_deal"))
    assert diagnose(vetoed, TaskConstraint("approve", decision_id="approve_deal")).reason == VETO
    with pytest.raises(TransitionError):
        apply(vetoed, Approve("approve_deal", "approver"))


def test_sla_tick_breaches_and_external_information_is_explicit() -> None:
    state = _base()
    later = apply(state, Tick(5))
    assert later.time == 5
    assert later.slas["clock"].breached is True
    assert "sla:clock" in later.escalations
    constraint = TaskConstraint("review", external_relation_id="buyer_profile", ready=True)
    assert diagnose(state, constraint).reason == EXTERNAL_INFORMATION_UNAVAILABLE
    received = apply(state, ReceiveExternalInformation("buyer_profile"))
    assert diagnose(received, constraint).reason == CAN_PROGRESS


def test_participation_does_not_create_authority_or_a_handoff() -> None:
    state = _base()
    before_grants = set(state.authority)
    after = apply(apply(state, Participate("R1", "ApproveDeal")), Participate("R2", "ApproveDeal"))
    assert set(after.authority) == before_grants
    names = {relation.name for relation in after.relations.values()}
    assert "handoff" not in names
    assert tuple(field.name for field in fields(Task)) == ("task_id", "deal_id", "task_type", "name")
    assert baseline_one_occurrence_matches_v1() is True


def test_docx_separations_stay_explicit() -> None:
    state = _base()
    state.people["ada"] = Person("ada")
    state.capabilities["security_review"] = Capability("security_review", "Security Review")
    state.business_units["enterprise"] = BusinessUnit("enterprise", "seller")
    state.teams["deal_team"] = Team("deal_team")
    held = apply(state, AssignRole("ada", "approver"))
    capable = apply(held, AssignCapability("legal", "security_review"))
    right = apply(capable, GrantDecisionRight("r1", "clerk", "approve_deal", "advise"))
    assert "ada" in right.people
    assert "ada" not in right.resources
    assert "has_capability" in {item.name for item in right.relations.values()}
    assert "responsible_for" not in {item.name for item in right.relations.values()}
    assert "advise" in {item.name for item in right.relations.values()}
    assert set(right.authority) == set(state.authority)
    assert right.business_units["enterprise"].organization_id == "seller"
    assert "deal_team" not in right.departments
    customer = ExternalRelation("ctx_a", "buyer", "seller", "profile", kind="customer", context_id="deal_a")
    partner = ExternalRelation("ctx_b", "buyer", "seller", "profile", kind="partner", context_id="deal_b")
    assert customer.kind != partner.kind
    assert customer.external_organization_id == partner.external_organization_id
