"""Macro records stay outside the micro transition."""

from pathlib import Path

import dealos.org.macro as macro
from dealos.experiments.runner import rollout
from dealos.generator.generate import _TEMPLATE, generate_scenario
from dealos.generator.presets import RESOURCE_IDS, get_preset
from dealos.org.macro import (
    LAYER,
    Actor,
    AuthorityGrant,
    AuthorityState,
    DealTaskBinding,
    Epistemic,
    EscalationRule,
    InformationLink,
    InvolvementChange,
    InvolvementEvent,
    InvolvementReason,
    OrganizationRecord,
    OrganizationRecordError,
    OrgSystem,
    ResourceControl,
    ResourceRight,
    Role,
    Side,
    check_against_micro,
    describe_binding,
)
from dealos.policies.fifo import FIFOPolicy


H = Epistemic.HYPOTHESIS
ROOT = Path(__file__).resolve().parents[1]
MACRO_SOURCE = (ROOT / "src" / "dealos" / "org" / "macro.py").read_text(encoding="utf-8")


def test_layer_is_macro_and_does_not_import_the_micro_runtime() -> None:
    assert LAYER == "macro"
    for forbidden in (
        "dealos.sim",
        "dealos.policies",
        "dealos.generator",
        "dealos.experiments",
        "dealos.domain",
    ):
        assert forbidden not in MACRO_SOURCE
    assert "reports_to" not in MACRO_SOURCE
    assert not hasattr(macro, "problem_class")


def test_empty_record_loads_no_candidate_department() -> None:
    record = OrganizationRecord(name="blank")
    assert record.systems == ()
    assert record.grants == ()
    assert record.bindings == ()


def test_authority_state_rejects_a_continuous_score() -> None:
    try:
        AuthorityState("0.73")
    except ValueError:
        return
    raise AssertionError("continuous authority was accepted")


def test_bridge_keeps_approval_information_and_capacity_apart() -> None:
    record = _security_bridge()
    binding = record.bindings[0]
    account = describe_binding(record, binding)
    assert account.distinct_approver
    assert account.executor_grants[0].state is AuthorityState.EXECUTE
    assert account.approver_grants[0].state is AuthorityState.APPROVE
    assert account.missing_info == ()
    assert account.escalation_rules[0].to_role_id == "executive_sponsor"
    assert record.controls[0].right is ResourceRight.ALLOCATE
    assert record.links[0].info_kind == "architecture"
    assert not hasattr(account, "problem_class")


def test_information_link_does_not_create_an_authority_grant() -> None:
    record = _security_bridge()
    assert len(record.links) == 1
    assert all(grant.role_id != "technical_system" for grant in record.grants)


def test_same_role_may_execute_and_approve_when_the_record_says_so() -> None:
    record = OrganizationRecord(
        name="collapsed",
        systems=(
            OrgSystem(
                "security",
                "security",
                frozenset({"architecture"}),
                frozenset(),
                frozenset({"approve_review"}),
                frozenset({"review"}),
                frozenset(),
                H,
            ),
        ),
        roles=(Role("reviewer", "security", H),),
        bindings=(
            DealTaskBinding(
                task_type="security",
                system_id="security",
                executing_role_id="reviewer",
                approving_role_id="reviewer",
                decision_kind="approve_review",
                required_info=frozenset(),
                status=H,
            ),
        ),
        grants=(
            AuthorityGrant("reviewer", "approve_review", frozenset(), AuthorityState.EXECUTE, H),
        ),
    )
    assert describe_binding(record, record.bindings[0]).distinct_approver is False


def test_external_involvement_is_a_reason_on_the_deal() -> None:
    record = OrganizationRecord(
        name="external",
        systems=(OrgSystem("customer", "customer", frozenset(), frozenset(), frozenset(), frozenset(), frozenset(), H),),
        roles=(Role("customer_legal", "customer", H),),
        actors=(Actor("buyer-counsel", Side.EXTERNAL, frozenset({"customer_legal"}), H),),
        involvement=(
            InvolvementEvent("deal-1", "day-15", "customer_legal", InvolvementChange.ENTER, InvolvementReason.EXTERNAL, H),
        ),
    )
    event = record.involvement[0]
    assert event.reason is InvolvementReason.EXTERNAL
    assert record.actors[0].side is Side.EXTERNAL


def test_record_rejects_an_unconditional_escalation_and_a_mismatched_bridge() -> None:
    system = OrgSystem(
        "legal",
        "legal",
        frozenset(),
        frozenset(),
        frozenset({"approve_contract"}),
        frozenset(),
        frozenset(),
        H,
    )
    counsel = Role("counsel", "legal", H)
    try:
        OrganizationRecord(
            name="bad-escalation",
            systems=(system,),
            roles=(counsel,),
            escalations=(EscalationRule("approve_contract", frozenset(), "counsel", "counsel", H),),
        )
    except OrganizationRecordError as error:
        assert any("empty condition" in message for message in error.messages)
    else:
        raise AssertionError("empty escalation condition was accepted")
    try:
        OrganizationRecord(
            name="bad-bridge",
            systems=(
                system,
                OrgSystem("sales", "sales", frozenset(), frozenset(), frozenset(), frozenset(), frozenset(), H),
            ),
            roles=(counsel, Role("ae", "sales", H)),
            bindings=(
                DealTaskBinding(
                    task_type="legal",
                    system_id="legal",
                    executing_role_id="ae",
                    required_info=frozenset(),
                    status=H,
                ),
            ),
        )
    except OrganizationRecordError as error:
        assert any("outside system" in message for message in error.messages)
    else:
        raise AssertionError("executor outside the bound system was accepted")


def test_approver_requires_a_declared_decision() -> None:
    try:
        OrganizationRecord(
            name="approver",
            systems=(
                OrgSystem("legal", "legal", frozenset(), frozenset(), frozenset(), frozenset(), frozenset(), H),
            ),
            roles=(Role("counsel", "legal", H), Role("manager", "legal", H)),
            bindings=(
                DealTaskBinding(
                    task_type="legal",
                    system_id="legal",
                    executing_role_id="counsel",
                    approving_role_id="manager",
                    required_info=frozenset(),
                    status=H,
                ),
            ),
        )
    except OrganizationRecordError as error:
        assert any("no decision" in message for message in error.messages)
    else:
        raise AssertionError("approver without a decision was accepted")


def test_output_must_be_declared_before_it_can_feed_another_system() -> None:
    try:
        OrganizationRecord(
            name="link",
            systems=(
                OrgSystem("technical", "technical", frozenset(), frozenset(), frozenset(), frozenset(), frozenset(), H),
                OrgSystem("security", "security", frozenset({"architecture"}), frozenset(), frozenset(), frozenset(), frozenset(), H),
            ),
            links=(InformationLink("technical", "architecture", "security", frozenset(), H),),
        )
    except OrganizationRecordError as error:
        assert any("not an output" in message for message in error.messages)
    else:
        raise AssertionError("undeclared output was accepted as information flow")


def test_bridge_identifiers_must_exist_on_the_micro_model() -> None:
    record = _security_bridge()
    task_types = frozenset(task_type for _name, task_type, _preds, _optional in _TEMPLATE)
    check_against_micro(record, resource_ids=frozenset(RESOURCE_IDS), task_types=task_types)
    try:
        check_against_micro(
            record,
            resource_ids=frozenset({"ae"}),
            task_types=task_types,
        )
    except OrganizationRecordError as error:
        assert any("not a micro resource" in message for message in error.messages)
    else:
        raise AssertionError("unknown resource control was accepted")


def test_micro_rollout_is_unchanged() -> None:
    scenario = generate_scenario(get_preset("balanced"), seed=0)
    result = rollout(scenario, FIFOPolicy())
    assert result.completed_deals == 2
    assert result.steps == 40


def _security_bridge() -> OrganizationRecord:
    """A labeled hypothesis used only to exercise the schema."""

    return OrganizationRecord(
        name="hypothesis-security",
        scale_band="unspecified",
        systems=(
            OrgSystem(
                "technical",
                "technical",
                frozenset(),
                frozenset(),
                frozenset(),
                frozenset(),
                frozenset({"architecture"}),
                H,
            ),
            OrgSystem(
                "security",
                "security",
                frozenset({"architecture"}),
                frozenset({"review_status"}),
                frozenset({"approve_review"}),
                frozenset({"review"}),
                frozenset({"risk_assessment"}),
                H,
            ),
            OrgSystem(
                "executive",
                "executive",
                frozenset(),
                frozenset(),
                frozenset(),
                frozenset(),
                frozenset(),
                H,
            ),
        ),
        roles=(
            Role("reviewer", "security", H),
            Role("security_manager", "security", H),
            Role("executive_sponsor", "executive", H),
        ),
        actors=(
            Actor("person-reviewer", Side.INTERNAL, frozenset({"reviewer"}), H),
            Actor("person-manager", Side.INTERNAL, frozenset({"security_manager"}), H),
        ),
        grants=(
            AuthorityGrant("reviewer", "approve_review", frozenset(), AuthorityState.EXECUTE, H),
            AuthorityGrant("security_manager", "approve_review", frozenset(), AuthorityState.APPROVE, H),
            AuthorityGrant(
                "security_manager",
                "approve_review",
                frozenset({"high_risk"}),
                AuthorityState.NONE,
                H,
            ),
        ),
        links=(InformationLink("technical", "architecture", "security", frozenset({"reviewer"}), H),),
        controls=(ResourceControl("security", "reviewer", ResourceRight.ALLOCATE, H),),
        bindings=(
            DealTaskBinding(
                task_type="security",
                task_name="security_review",
                system_id="security",
                executing_role_id="reviewer",
                approving_role_id="security_manager",
                decision_kind="approve_review",
                required_info=frozenset({"architecture"}),
                status=H,
            ),
        ),
        escalations=(
            EscalationRule(
                "approve_review",
                frozenset({"high_risk"}),
                "security_manager",
                "executive_sponsor",
                H,
            ),
        ),
        involvement=(
            InvolvementEvent("deal-1", "day-1", "reviewer", InvolvementChange.ENTER, InvolvementReason.TASK_READY, H),
            InvolvementEvent("deal-1", "day-30", "executive_sponsor", InvolvementChange.ENTER, InvolvementReason.ESCALATION, H),
        ),
    )
