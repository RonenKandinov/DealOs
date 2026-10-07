"""Same Micro readiness, different Macro state, different progress."""

from dealos.experiments.macro_micro_integration import comparison_rows, invariant_failures, run_all
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1


def test_same_micro_readiness_gets_different_macro_outcomes() -> None:
    rows = comparison_rows()
    assert len({row.progress_before for row in rows}) == 1
    assert all(row.initial_micro_ready for row in rows)
    assert [row.blocking_reason_before for row in rows] == [
        "can_progress",
        "capacity_unavailable",
        "information_unavailable",
        "authority_unavailable",
        "veto",
        "external_information_unavailable",
    ]
    assert rows[0].progress_after == 1.0
    assert all(row.progress_after == 0.0 for row in rows[1:])
    assert all(row.passed for row in rows)
    assert not any(row.in_blocked_tasks for row in rows)


def test_release_produce_receive_and_veto_change_the_gate() -> None:
    rows = {row.scenario_id: row for row in run_all()}
    assert rows["C-capacity"].passed
    assert rows["C-information"].passed
    assert rows["D-veto"].blocking_reason_before == "veto"
    assert rows["D-external-after"].progress_after == 1.0
    assert rows["A-capacity"].diagnosis.evidence


def test_invariants_and_seed_fingerprint() -> None:
    assert invariant_failures() == ()
    assert baseline_one_occurrence_matches_v1() is True
