"""Representation evolution: gap classification, the ground-truth representation gap,
candidate evaluation, holdout generalization, anti-leakage, and regression.

Merged from test_representation_gap and test_representation_gap_ground_truth. Every test
body is unchanged.
"""

import inspect
from dataclasses import fields, replace
from pathlib import Path

from dealos.experiments.macro_micro_integration import invariant_failures
from dealos.experiments.macro_micro_multiconstraint import CONSTRAINT, TASK_NAME
from dealos.experiments.representation_gap import (
    NO_GAP,
    OBSERVATION_GAP,
    REPRESENTATION_GAP,
    SEMANTIC_GAP,
    Observation,
    Proposal,
    candidate_accepted,
    classify,
    integration_still_passes,
    run_all_gaps,
    satisfied_state,
)
from dealos.experiments.representation_gap_ground_truth import (
    BLOCKED,
    HIDDEN_FIELDS,
    HOLDOUT_IDS,
    NAMED_IDS,
    PROGRESS,
    PROPOSAL_IDS,
    PUBLIC_FIELDS,
    constraint_for,
    current_prediction,
    evaluate,
    ground_truth_outcome,
    grid_worlds,
    named_worlds,
    predict,
    project_observation,
    project_org,
    propose,
    run_experiment,
)
from dealos.org.operating.bridge import CAN_PROGRESS, diagnose
from dealos.org.operating.entities import TaskConstraint
from dealos.org.operating.state import OrgState
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1

ROOT = Path(__file__).parents[1]


def _by_name():
    return {row.scenario: row for row in run_all_gaps()}


def _complete(progress: float) -> Observation:
    return Observation(
        task_ready=True,
        capacity_available=True,
        required_information_available=True,
        external_information_available=True,
        authority_available=True,
        veto=False,
        observed_progress=progress,
    )


def _worlds():
    return {world.scenario_id: world for world in named_worlds()}


def _results():
    named, grid, candidates, vectors = run_experiment()
    return {r.world.scenario_id: r for r in named}, grid, {c.name: c for c in candidates}, {v.name: v for v in vectors}


# ---- Observation/Representation/Semantic gap classification ----


def test_satisfied_constraints_predict_can_progress_on_a_ready_task() -> None:
    diagnosis = diagnose(satisfied_state(), CONSTRAINT)
    hidden = _by_name()["hidden_causal_observation"]
    assert diagnosis.reason == CAN_PROGRESS
    assert diagnosis.blocking_reasons == ()
    assert diagnosis.ready is True
    assert hidden.current_model_prediction == CAN_PROGRESS
    assert TASK_NAME == "deal_A:A1"


def test_hidden_outcome_is_an_observation_gap() -> None:
    row = _by_name()["hidden_causal_observation"]
    assert row.observations_available is False
    assert row.observed_outcome == "hidden"
    assert row.classification == OBSERVATION_GAP
    assert row.classification != REPRESENTATION_GAP
    withheld = Observation(
        task_ready=True,
        capacity_available=True,
        required_information_available=True,
        external_information_available=True,
        authority_available=True,
        veto=False,
        observed_progress=None,
    )
    assert classify(CAN_PROGRESS, withheld, Proposal("TimeGapIsWaiting", ("time_gap_is_waiting",))) == OBSERVATION_GAP


def test_complete_unexplained_non_progress_is_a_representation_gap() -> None:
    row = _by_name()["unexplained_non_progress"]
    assert row.observations_available is True
    assert row.current_model_prediction == CAN_PROGRESS
    assert row.observed_outcome == "0.0"
    assert row.classification == REPRESENTATION_GAP
    assert row.candidate == "UnmodeledConstraint"
    assert row.accepted is True
    assert candidate_accepted(Proposal("UnmodeledConstraint")) is True


def test_unsupported_story_is_a_semantic_gap_and_is_rejected() -> None:
    row = _by_name()["unsupported_causal_story"]
    story = Proposal("TimeGapIsWaiting", ("time_gap_is_waiting",))
    assert row.classification == SEMANTIC_GAP
    assert row.accepted is False
    assert candidate_accepted(story) is False
    assert classify(CAN_PROGRESS, _complete(0.0), story) == SEMANTIC_GAP
    assert classify(CAN_PROGRESS, _complete(0.0), Proposal("CustomerDelay")) == SEMANTIC_GAP


def test_matching_progress_has_no_gap() -> None:
    row = _by_name()["explained_progress"]
    assert row.observations_available is True
    assert row.current_model_prediction == CAN_PROGRESS
    assert float(row.observed_outcome) == 1.0
    assert row.classification == NO_GAP
    assert row.candidate == ""
    assert row.accepted is False


def test_the_candidate_slot_is_not_installed() -> None:
    names = {item.name for item in fields(TaskConstraint)}
    assert "UnmodeledConstraint" not in names
    source = Path(__file__).parents[1].joinpath("src/dealos/org/operating/entities.py").read_text(encoding="utf-8")
    assert "UnmodeledConstraint" not in source


# ---- Ground-truth representation gap ----


def test_hidden_rule_changes_the_outcome_with_holders_fixed() -> None:
    g1 = _worlds()["G1"]
    assert ground_truth_outcome(g1) == BLOCKED
    assert ground_truth_outcome(replace(g1, rule=replace(g1.rule, active=False))) == PROGRESS
    g2 = _worlds()["G2"]
    assert ground_truth_outcome(g2) == PROGRESS
    assert ground_truth_outcome(replace(g2, rule=replace(g2.rule, required_clear=2))) == BLOCKED


def test_current_representation_has_no_field_for_the_rule() -> None:
    g1 = _worlds()["G1"]
    state = project_org(g1)
    assert state.governance == {}
    assert "DutyExclusion" not in {type(value).__name__ for mapping in vars(state).values() if isinstance(mapping, dict) for value in mapping.values()}
    assert diagnose(state, constraint_for(g1)).reason == CAN_PROGRESS
    assert diagnose(state, constraint_for(g1)).blocking_reasons == ()


def test_g1_is_a_real_mismatch_and_a_representation_gap() -> None:
    results, _, _, _ = _results()
    g1 = results["G1"]
    assert g1.current_model_prediction == CAN_PROGRESS
    assert g1.ground_truth_outcome == BLOCKED
    assert g1.row.observation.observed_progress == 0.0
    assert g1.mismatch is True
    assert g1.classification == REPRESENTATION_GAP


def test_g2_matches_with_the_same_representation() -> None:
    results, _, _, _ = _results()
    g2 = results["G2"]
    assert g2.current_model_prediction == CAN_PROGRESS
    assert g2.ground_truth_outcome == PROGRESS
    assert g2.row.observation.observed_progress == 1.0
    assert g2.mismatch is False
    assert g2.classification == NO_GAP
    assert current_prediction(_worlds()["G1"]) == current_prediction(_worlds()["G2"])


def test_g3_and_g4_follow_the_parameter() -> None:
    results, _, _, _ = _results()
    assert results["G3"].ground_truth_outcome == BLOCKED
    assert results["G3"].classification == REPRESENTATION_GAP
    assert results["G4"].ground_truth_outcome == PROGRESS
    assert results["G4"].classification == NO_GAP
    g3 = _worlds()["G3"]
    assert ground_truth_outcome(replace(g3, rule=replace(g3.rule, required_clear=1))) == PROGRESS


def test_the_candidate_is_not_installed() -> None:
    assert "DutyExclusion" not in {item.name for item in fields(TaskConstraint)}
    assert "DutyExclusion" not in {item.name for item in fields(OrgState)}
    for name in ("entities.py", "state.py", "bridge.py", "transition.py"):
        source = ROOT.joinpath("src/dealos/org/operating", name).read_text(encoding="utf-8")
        assert "DutyExclusion" not in source


# ---- Candidate evaluation ----


def test_negative_controls_progress_and_the_fitted_candidate_leaves_them_alone() -> None:
    results, _, candidates, vectors = _results()
    for sid in ("G5", "G6"):
        assert results[sid].ground_truth_outcome == PROGRESS
        assert results[sid].mismatch is False
        assert predict(candidates["DutyExclusion"], results[sid].row, results[sid].current_model_prediction) == PROGRESS
    assert vectors["DutyExclusion"].specificity is True
    assert vectors["DutyExclusion"].regression is True


def test_unsupported_semantic_candidate_is_rejected() -> None:
    results, _, candidates, vectors = _results()
    story = candidates["TimeGapIsWaiting"]
    g1 = results["G1"]
    assert classify(g1.current_model_prediction, g1.row.observation, story.proposal()) == SEMANTIC_GAP
    assert vectors["TimeGapIsWaiting"].admissible is False
    assert vectors["TimeGapIsWaiting"].semantic_safety is False
    assert vectors["TimeGapIsWaiting"].supported is False
    assert vectors["UnmodeledConstraint"].admissible is True
    assert vectors["UnmodeledConstraint"].supported is False


# ---- Holdout/generalization ----


def test_candidates_are_scored_on_every_named_world_and_the_grid() -> None:
    results, grid, candidates, vectors = _results()
    for candidate in candidates.values():
        for sid in NAMED_IDS:
            assert predict(candidate, results[sid].row, results[sid].current_model_prediction) in {PROGRESS, BLOCKED}
    assert vectors["DutyExclusion"].coverage == len(NAMED_IDS)
    assert vectors["DutyExclusion"].contradiction_resolution is True
    assert vectors["DutyExclusion"].supported is True
    assert vectors["DutyExclusion"].grid_total == len(grid) == 48
    assert vectors["DutyExclusion"].grid_correct > vectors["DecisionQuorum"].grid_correct
    assert dict(vectors["DecisionQuorum"].grid_failures).get("prior_not_holder", 0) > 0
    assert dict(vectors["DutyExclusion"].grid_failures).get("prior_not_holder", 0) == 0


def test_proposal_is_separate_from_holdout() -> None:
    assert PROPOSAL_IDS == ("G1", "G2", "G3")
    assert HOLDOUT_IDS == ("G4", "G5", "G6")
    results, _, _, _ = _results()
    proposal_rows = tuple(results[sid].row for sid in PROPOSAL_IDS)
    fitted = {c.name: c for c in propose(proposal_rows)}
    assert dict(fitted["DutyExclusion"].thresholds) == {"approve_deal": 1, "approve_budget": 2}
    assert "file_report" not in dict(fitted["DutyExclusion"].thresholds)
    source = inspect.getsource(propose)
    assert "ground_truth" not in source
    assert ".rule" not in source
    assert "required_clear" not in source
    assert "World" not in source
    holdout = tuple(results[sid] for sid in HOLDOUT_IDS)
    vector = evaluate(fitted["DutyExclusion"], tuple(results[sid] for sid in NAMED_IDS), (), True)
    assert vector.holdout_matches == len(holdout)


# ---- Anti-leakage ----


def test_observation_has_no_hidden_field() -> None:
    for world in named_worlds() + grid_worlds()[:8]:
        row = project_observation(world, ground_truth_outcome(world))
        keys = set(row.fields())
        assert keys <= PUBLIC_FIELDS
        assert keys.isdisjoint(HIDDEN_FIELDS)
        text = ";".join(f"{k}={v}" for k, v in row.fields().items())
        assert "required_clear" not in text and "active=" not in text and "DutyExclusion" not in text


# ---- Regression ----


def test_integration_and_seed_fingerprint_stay_in_place() -> None:
    assert integration_still_passes() is True
    assert baseline_one_occurrence_matches_v1() is True


def test_integration_and_fingerprint_stay_in_place() -> None:
    assert invariant_failures() == ()
    assert baseline_one_occurrence_matches_v1() is True
