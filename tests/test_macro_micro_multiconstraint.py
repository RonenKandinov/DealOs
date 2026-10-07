"""One ready Micro task, several Macro constraints, one explicit change at a time."""

from dealos.experiments.macro_micro_multiconstraint import (
    CONSTRAINT,
    DECISION,
    EXTERNAL_PROFILE,
    POOL,
    PROFILE,
    alternate_trace,
    initial_state,
    invariant_failures,
    isolated_trace,
    primary_trace,
    veto_trace,
)
from dealos.org.operating.bridge import (
    AUTHORITY_UNAVAILABLE,
    CAN_PROGRESS,
    CAPACITY_UNAVAILABLE,
    EXTERNAL_INFORMATION_UNAVAILABLE,
    INFORMATION_UNAVAILABLE,
    VETO,
    diagnose,
)
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1


def _reasons(row) -> set[str]:
    return {blocker.reason for blocker in row.diagnosis.blocking_reasons}


def _evidence(row, reason: str) -> dict[str, str]:
    blocker = next(item for item in row.diagnosis.blocking_reasons if item.reason == reason)
    return dict(blocker.evidence)


def test_initial_state_lists_every_blocker_while_micro_stays_ready() -> None:
    row = primary_trace()[0]
    assert row.micro_ready is True
    assert row.micro_readiness == 1.0
    assert row.progress_before == 0.0
    assert row.in_blocked_tasks is False
    assert row.eligible is False
    assert _reasons(row) == {
        CAPACITY_UNAVAILABLE,
        INFORMATION_UNAVAILABLE,
        AUTHORITY_UNAVAILABLE,
        EXTERNAL_INFORMATION_UNAVAILABLE,
    }
    assert row.diagnosis.reason == CAPACITY_UNAVAILABLE
    assert row.diagnosis.task_id == "deal_A:A1"
    capacity = _evidence(row, CAPACITY_UNAVAILABLE)
    assert capacity["pool_id"] == POOL
    assert capacity["available"] == f"{row.state.capacity[POOL].available}"
    assert capacity["required"] == "1"
    information = _evidence(row, INFORMATION_UNAVAILABLE)
    assert information["information_id"] == PROFILE
    assert information["available"] == "False"
    authority = _evidence(row, AUTHORITY_UNAVAILABLE)
    assert authority["decision_id"] == DECISION
    assert authority["authority_holders"] == ""
    external = _evidence(row, EXTERNAL_INFORMATION_UNAVAILABLE)
    assert external["external_relation_id"] == "buyer_profile"
    assert external["information_id"] == EXTERNAL_PROFILE
    assert external["available"] == "False"
    assert row.state.information[PROFILE].available is False
    assert row.state.information[EXTERNAL_PROFILE].available is False


def test_each_event_removes_only_its_constraint_and_progress_waits() -> None:
    rows = primary_trace()
    assert _reasons(rows[1]) == _reasons(rows[0]) - {CAPACITY_UNAVAILABLE}
    assert _reasons(rows[2]) == _reasons(rows[1]) - {INFORMATION_UNAVAILABLE}
    assert _reasons(rows[3]) == _reasons(rows[2]) - {EXTERNAL_INFORMATION_UNAVAILABLE}
    assert _reasons(rows[4]) == set()
    assert rows[4].diagnosis.reason == CAN_PROGRESS
    assert [row.eligible for row in rows] == [False, False, False, False, True]
    assert [row.progress_after for row in rows] == [0.0, 0.0, 0.0, 0.0, 1.0]
    assert all(left.diagnosis.blocking_reasons != right.diagnosis.blocking_reasons for left, right in zip(rows, rows[1:]))
    assert rows[1].state.information[PROFILE].available is False
    assert rows[1].state.authority == {}
    assert rows[2].state.capacity[POOL].available == rows[1].state.capacity[POOL].available == 1.0
    assert rows[2].state.information[EXTERNAL_PROFILE].available is False
    assert rows[3].state.authority == {}
    assert rows[3].state.information[PROFILE].available is True
    assert rows[3].state.information[EXTERNAL_PROFILE].available is True
    assert rows[4].progress_before == 0.0


def test_one_event_from_the_initial_state_does_not_clear_another_constraint() -> None:
    start = _reasons(primary_trace()[0])
    isolated = {row.state_id: row for row in isolated_trace()}
    assert _reasons(isolated["I-release"]) == start - {CAPACITY_UNAVAILABLE}
    assert isolated["I-release"].state.information[PROFILE].available is False
    assert _reasons(isolated["I-produce"]) == start - {INFORMATION_UNAVAILABLE}
    assert AUTHORITY_UNAVAILABLE in _reasons(isolated["I-produce"])
    assert isolated["I-produce"].state.capacity[POOL].available == 0.0
    assert _reasons(isolated["I-receive"]) == start - {EXTERNAL_INFORMATION_UNAVAILABLE}
    assert isolated["I-receive"].state.information[PROFILE].available is False
    assert _reasons(isolated["I-grant"]) == start - {AUTHORITY_UNAVAILABLE}
    assert isolated["I-grant"].state.capacity[POOL].available == 0.0
    assert all(row.progress_after == 0.0 and row.eligible is False for row in isolated.values())


def test_another_event_order_changes_the_intermediate_diagnosis() -> None:
    primary = primary_trace()
    alternate = alternate_trace()
    assert _reasons(primary[0]) == _reasons(alternate[0])
    assert _reasons(alternate[1]) == _reasons(alternate[0]) - {AUTHORITY_UNAVAILABLE}
    assert CAPACITY_UNAVAILABLE in _reasons(alternate[1])
    assert _reasons(alternate[2]) == _reasons(alternate[1]) - {CAPACITY_UNAVAILABLE}
    assert _reasons(alternate[3]) == _reasons(alternate[2]) - {INFORMATION_UNAVAILABLE}
    assert _reasons(alternate[4]) == set()
    assert alternate[4].eligible is True
    assert alternate[4].progress_after == 1.0
    assert [_reasons(row) for row in primary[1:-1]] != [_reasons(row) for row in alternate[1:-1]]
    fresh = diagnose(alternate[2].state, CONSTRAINT)
    assert {item.reason for item in fresh.blocking_reasons} == _reasons(alternate[2])


def test_veto_blocks_a_granted_decision_and_clearing_it_leaves_other_blockers() -> None:
    mixed = [row for row in veto_trace() if row.sequence == "veto-with-capacity"]
    sole = [row for row in veto_trace() if row.sequence == "veto-only"]
    assert _reasons(mixed[0]) == {CAPACITY_UNAVAILABLE}
    assert VETO in _reasons(mixed[1])
    assert AUTHORITY_UNAVAILABLE not in _reasons(mixed[1])
    assert mixed[1].eligible is False
    assert mixed[1].progress_after == 0.0
    assert _reasons(mixed[2]) == {CAPACITY_UNAVAILABLE}
    assert mixed[2].state.vetoes["v1"].active is False
    assert _reasons(sole[0]) == {VETO}
    assert sole[0].state.authority["grant"].holder_id == "approver"
    assert sole[0].eligible is False
    assert sole[0].progress_after == 0.0
    assert sole[1].diagnosis.reason == CAN_PROGRESS
    assert sole[1].progress_after == 1.0


def test_evidence_matches_the_state_being_diagnosed() -> None:
    state = initial_state()
    state.capacity[POOL] = type(state.capacity[POOL])(POOL, 1.0, 0.0)
    diagnosis = diagnose(state, CONSTRAINT)
    capacity = dict(next(item.evidence for item in diagnosis.blocking_reasons if item.reason == CAPACITY_UNAVAILABLE))
    assert capacity["available"] == "0.0"
    assert capacity["pool_id"] == state.capacity[POOL].pool_id
    assert diagnosis.task_id == CONSTRAINT.task_id


def test_invariants_and_the_existing_micro_baseline() -> None:
    assert invariant_failures() == ()
    assert baseline_one_occurrence_matches_v1() is True
