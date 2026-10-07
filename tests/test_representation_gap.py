"""Missing observation, missing representation, and unsupported semantics stay distinct."""

from dataclasses import fields
from pathlib import Path

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
from dealos.experiments.macro_micro_multiconstraint import CONSTRAINT, TASK_NAME
from dealos.org.operating.bridge import CAN_PROGRESS, diagnose
from dealos.org.operating.entities import TaskConstraint
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1


def _by_name():
    return {row.scenario: row for row in run_all_gaps()}


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


def test_integration_and_seed_fingerprint_stay_in_place() -> None:
    assert integration_still_passes() is True
    assert baseline_one_occurrence_matches_v1() is True


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
