"""Hidden rule in the world, no field in the gate, candidates scored on held-out worlds."""

import inspect
from dataclasses import fields, replace
from pathlib import Path

from dealos.experiments.representation_gap import NO_GAP, REPRESENTATION_GAP, SEMANTIC_GAP, classify
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
from dealos.experiments.macro_micro_integration import invariant_failures
from dealos.org.operating.bridge import CAN_PROGRESS, diagnose
from dealos.org.operating.entities import TaskConstraint
from dealos.org.operating.state import OrgState
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1

ROOT = Path(__file__).parents[1]


def _worlds():
    return {world.scenario_id: world for world in named_worlds()}


def _results():
    named, grid, candidates, vectors = run_experiment()
    return {r.world.scenario_id: r for r in named}, grid, {c.name: c for c in candidates}, {v.name: v for v in vectors}


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


def test_negative_controls_progress_and_the_fitted_candidate_leaves_them_alone() -> None:
    results, _, candidates, vectors = _results()
    for sid in ("G5", "G6"):
        assert results[sid].ground_truth_outcome == PROGRESS
        assert results[sid].mismatch is False
        assert predict(candidates["DutyExclusion"], results[sid].row, results[sid].current_model_prediction) == PROGRESS
    assert vectors["DutyExclusion"].specificity is True
    assert vectors["DutyExclusion"].regression is True


def test_the_candidate_is_not_installed() -> None:
    assert "DutyExclusion" not in {item.name for item in fields(TaskConstraint)}
    assert "DutyExclusion" not in {item.name for item in fields(OrgState)}
    for name in ("entities.py", "state.py", "bridge.py", "transition.py"):
        source = ROOT.joinpath("src/dealos/org/operating", name).read_text(encoding="utf-8")
        assert "DutyExclusion" not in source


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


def test_integration_and_fingerprint_stay_in_place() -> None:
    assert invariant_failures() == ()
    assert baseline_one_occurrence_matches_v1() is True


def test_observation_has_no_hidden_field() -> None:
    for world in named_worlds() + grid_worlds()[:8]:
        row = project_observation(world, ground_truth_outcome(world))
        keys = set(row.fields())
        assert keys <= PUBLIC_FIELDS
        assert keys.isdisjoint(HIDDEN_FIELDS)
        text = ";".join(f"{k}={v}" for k, v in row.fields().items())
        assert "required_clear" not in text and "active=" not in text and "DutyExclusion" not in text


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
