"""Same Micro deal, different Macro state, different progress."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from dealos.diagnostics.manual_scenario import chain_debug_scenario
from dealos.domain.models import AllocationAction
from dealos.org.operating.bridge import CAN_PROGRESS, Diagnosis, diagnose
from dealos.org.operating.entities import (
    AuthorityGrant,
    CapacityPool,
    Decision,
    ExternalRelation,
    InformationObject,
    Organization,
    System,
    TaskConstraint,
    Veto,
)
from dealos.org.operating.state import OrgState
from dealos.org.operating.transition import (
    Allocate,
    Approve,
    ConsumeInformation,
    Delegate,
    IssueVeto,
    Participate,
    ProduceInformation,
    ReceiveExternalInformation,
    Reject,
    Release,
    Tick,
    Tick,
    TransitionError,
    apply,
)
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1
from dealos.sim.env import SalesEnvironment

TASK = ("deal_A", "deal_A:A1")
TASK_NAME = "deal_A:A1"


@dataclass(frozen=True)
class IntegrationRow:
    scenario_id: str
    task_id: str
    initial_micro_ready: bool
    macro_state_summary: str
    constraint_type: str
    eligible_before: bool
    blocking_reason_before: str
    progress_before: float
    event: str
    eligible_after: bool
    blocking_reason_after: str
    progress_after: float
    expected_result: str
    passed: bool
    in_blocked_tasks: bool
    diagnosis: Diagnosis


def run_all() -> tuple[IntegrationRow, ...]:
    return (*_capacity(), *_information(), *_authority(), *_external())


def comparison_rows() -> tuple[IntegrationRow, ...]:
    specs = (
        ("W1", "capacity available", _org(pool=1.0), TaskConstraint(TASK_NAME, capacity_pool_id="pool"), CAN_PROGRESS),
        ("W2", "capacity exhausted", _org(pool=0.0), TaskConstraint(TASK_NAME, capacity_pool_id="pool"), "capacity_unavailable"),
        ("W3", "information unavailable", _org(info=False), TaskConstraint(TASK_NAME, information_id="profile"), "information_unavailable"),
        ("W4", "authority unavailable", _org(grant=False), TaskConstraint(TASK_NAME, decision_id="approve_deal"), "authority_unavailable"),
        ("W5", "active veto", _org(veto=True), TaskConstraint(TASK_NAME, decision_id="approve_deal"), "veto"),
        ("W6", "external information unavailable", _org(info=False), TaskConstraint(TASK_NAME, external_relation_id="buyer_profile"), "external_information_unavailable"),
    )
    return tuple(_world(sid, summary, state, constraint, expected, "none") for sid, summary, state, constraint, expected in specs)


def invariant_failures() -> tuple[str, ...]:
    failures: list[str] = []
    state = _org(pool=1.0, info=True)
    try:
        apply(state, Allocate("pool", 2.0, "R1"))
        failures.append("over-allocation was accepted")
    except TransitionError:
        pass
    drained = apply(state, Allocate("pool", 1.0, "R1"))
    if drained.capacity["pool"].available < -1e-9:
        failures.append("available became negative")
    restored = apply(drained, Release("pool", 5.0))
    if restored.capacity["pool"].available > restored.capacity["pool"].total + 1e-9:
        failures.append("release exceeded total")
    try:
        apply(_org(info=False), ConsumeInformation("profile"))
        failures.append("consume succeeded while unavailable")
    except TransitionError:
        pass
    if not apply(_org(info=False), ProduceInformation("profile", "crm")).information["profile"].available:
        failures.append("produce did not make information available")
    before = set(_org().authority)
    participated = apply(_org(), Participate("R9", "ApproveDeal"))
    try:
        approved = apply(_org(grant=False), Approve("approve_deal", "stranger"))
        created = bool(approved.authority)
    except TransitionError:
        created = False
    if set(participated.authority) != before or created:
        failures.append("participation or approval created an authority grant")
    if not baseline_one_occurrence_matches_v1():
        failures.append("seed-0 fingerprint changed")
    ticked = apply(_org(), Tick(3))
    if ticked.time != 3:
        failures.append("tick did not set time")
    rejected = apply(_org(grant=True), Reject("approve_deal", "approver"))
    if rejected.decisions["approve_deal"].status != "rejected" or set(rejected.authority) != set(_org().authority):
        failures.append("reject changed authority")
    delegated = apply(_org(grant=True), Delegate("d1", "approver", "clerk", "approve_deal"))
    if "d1" not in delegated.delegations:
        failures.append("delegation was not stored")
    return tuple(failures)


def _capacity() -> tuple[IntegrationRow, ...]:
    constraint = TaskConstraint(TASK_NAME, capacity_pool_id="pool")
    return (
        _world("A-capacity", "pool available 1", _org(pool=1.0), constraint, CAN_PROGRESS, "none"),
        _world("B-capacity", "pool available 0", _org(pool=0.0), constraint, "capacity_unavailable", "none"),
        _world("C-capacity", "released back to 1", apply(_org(pool=0.0), Release("pool", 1.0)), constraint, CAN_PROGRESS, "Release"),
    )


def _information() -> tuple[IntegrationRow, ...]:
    constraint = TaskConstraint(TASK_NAME, information_id="profile")
    return (
        _world("A-information", "profile available", _org(info=True), constraint, CAN_PROGRESS, "none"),
        _world("B-information", "profile unavailable", _org(info=False), constraint, "information_unavailable", "none"),
        _world("C-information", "ProduceInformation", apply(_org(info=False), ProduceInformation("profile", "crm")), constraint, CAN_PROGRESS, "ProduceInformation"),
    )


def _authority() -> tuple[IntegrationRow, ...]:
    constraint = TaskConstraint(TASK_NAME, decision_id="approve_deal")
    holder = _org(grant=True)
    return (
        _world("A-authority", "grant approver, no veto", holder, constraint, CAN_PROGRESS, "none"),
        _world("B-authority", "no grant, no delegation", _org(grant=False), constraint, "authority_unavailable", "none"),
        _world("C-authority", "AuthorityGrant constructed", holder, constraint, CAN_PROGRESS, "constructor AuthorityGrant"),
        _world("D-veto", "grant plus IssueVeto", apply(holder, IssueVeto("v1", "security", "approve_deal")), constraint, "veto", "IssueVeto"),
    )


def _external() -> tuple[IntegrationRow, ...]:
    constraint = TaskConstraint(TASK_NAME, external_relation_id="buyer_profile")
    return (
        _world("D-external-before", "external profile unavailable", _org(info=False), constraint, "external_information_unavailable", "none"),
        _world("D-external-after", "ReceiveExternalInformation", apply(_org(info=False), ReceiveExternalInformation("buyer_profile")), constraint, CAN_PROGRESS, "ReceiveExternalInformation"),
    )


def _world(scenario_id: str, summary: str, state: OrgState, constraint: TaskConstraint, expected: str, event: str) -> IntegrationRow:
    progress_before, ready_flag, in_blocked = _micro_snapshot()
    before = diagnose(state, constraint)
    if before.reason == CAN_PROGRESS:
        progress_after, in_blocked_after = _step()
    else:
        progress_after = progress_before
        in_blocked_after = in_blocked
    moved = progress_after > progress_before
    passed = before.reason == expected and ((expected == CAN_PROGRESS and moved) or (expected != CAN_PROGRESS and not moved))
    return IntegrationRow(
        scenario_id,
        TASK_NAME,
        ready_flag,
        summary,
        _constraint_type(constraint),
        before.reason == CAN_PROGRESS,
        before.reason,
        progress_before,
        event,
        before.reason == CAN_PROGRESS,
        before.reason,
        progress_after,
        expected,
        passed,
        in_blocked_after,
        before,
    )


def _micro_snapshot() -> tuple[float, bool, bool]:
    env = SalesEnvironment(chain_debug_scenario())
    state = env.reset()
    progress = state.task_progress[TASK]
    return progress, TASK not in state.blocked_tasks and progress < 1.0, TASK in state.blocked_tasks


def _step() -> tuple[float, bool]:
    env = SalesEnvironment(chain_debug_scenario())
    state = env.reset()
    occurrence = state.primary_occurrence[TASK]
    env.step(AllocationAction({("deal_A", occurrence, "ae"): 1.0}))
    after = env.get_state()
    return after.task_progress[TASK], TASK in after.blocked_tasks


def _org(pool: float = 1.0, info: bool = True, grant: bool = True, veto: bool = False) -> OrgState:
    state = OrgState()
    state.organizations["seller"] = Organization("seller")
    state.organizations["buyer"] = Organization("buyer", external=True)
    state.capacity["pool"] = CapacityPool("pool", 1.0, pool)
    state.information["profile"] = InformationObject("profile", info)
    state.systems["crm"] = System("crm", "seller")
    state.decisions["approve_deal"] = Decision("approve_deal", "ApproveDeal", "open")
    state.external_relations["buyer_profile"] = ExternalRelation(
        "buyer_profile", "buyer", "seller", "profile", kind="configured", context_id="deal_A"
    )
    if grant:
        state.authority["grant"] = AuthorityGrant("grant", "approver", "role", "approve_deal")
    if veto:
        state.vetoes["v1"] = Veto("v1", "security", "approve_deal", True)
    return state


def _constraint_type(constraint: TaskConstraint) -> str:
    if constraint.capacity_pool_id:
        return "capacity"
    if constraint.external_relation_id:
        return "external_information"
    if constraint.information_id:
        return "information"
    if constraint.decision_id:
        return "decision"
    return "none"


def write_report(root: Path) -> str:
    rows = run_all()
    compared = comparison_rows()
    failures = invariant_failures()
    fingerprint = baseline_one_occurrence_matches_v1()
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "macro_micro_integration.csv", rows + compared)
    text = _render(rows, compared, failures, fingerprint)
    (docs / "macro_micro_integration_experiment.md").write_text(text, encoding="utf-8")
    return text


def _render(rows, compared, failures, fingerprint: bool) -> str:
    ok = not failures and all(row.passed for row in rows + compared) and fingerprint
    lines = [
        "# Macro-Micro integration experiment",
        "",
        "The question is whether the same Micro task, with the same readiness, gets a different outcome when only the Macro state changes.",
        "",
        "Each world resets chain_debug_scenario. deal_A:A1 starts at progress 0 and is not predecessor-blocked. diagnose is the gate. SalesEnvironment.step runs only when the reason is can_progress.",
        "",
        "## Comparison",
        "",
        "| World | Micro state | Macro difference | Eligibility | Reason | Progress |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in compared:
        lines.append(
            f"| {row.scenario_id} | ready, progress {row.progress_before} | {row.macro_state_summary} | {row.eligible_before} | {row.blocking_reason_before} | {row.progress_after} |"
        )
    lines.extend(["", "## Diagnosis", ""])
    for row in compared:
        evidence = ", ".join(f"{key}={value}" for key, value in row.diagnosis.evidence)
        lines.append(f"{row.scenario_id}: task {row.task_id}. reason {row.blocking_reason_before}. evidence {evidence}.")
    lines.extend(
        [
            "",
            "## Results",
            "",
            f"Rows passed: {sum(row.passed for row in rows + compared)}/{len(rows + compared)}.",
            f"Invariant failures: {len(failures)}.",
            f"Seed-0 FIFO fingerprint, 2 completed deals in 40 steps: {fingerprint}.",
            f"blocked_tasks contains deal_A:A1 in these worlds: {any(row.in_blocked_tasks for row in compared)}.",
            "",
            "This shows that the implemented Macro state can stop or allow the existing Micro update through an explicit TaskConstraint. It does not show that the ontology was recovered from a real deal log.",
            "",
            "MACRO MICRO COUPLING DEMONSTRATED" if ok else "MACRO MICRO COUPLING REQUIRES REVISION",
            "",
        ]
    )
    return "\n".join(lines)


def _write_csv(path: Path, rows: tuple[IntegrationRow, ...]) -> None:
    fields = (
        "scenario_id",
        "task_id",
        "initial_micro_ready",
        "macro_state_summary",
        "constraint_type",
        "eligible_before",
        "blocking_reason_before",
        "progress_before",
        "event",
        "eligible_after",
        "blocking_reason_after",
        "progress_after",
        "expected_result",
        "passed",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: getattr(row, name) for name in fields})


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    print(write_report(root))


if __name__ == "__main__":
    main()
