"""Controlled blockage checks. They do not change the frozen simulator."""

from dataclasses import fields

from dealos.domain.models import Task, TaskOccurrence
from dealos.experiments.blockage_diagnosis import (
    AMBIGUOUS,
    GAP,
    PARTIAL,
    all_results,
    capacity_bottleneck,
    fingerprint,
)
from dealos.macro_world.relations.models import RELATION_ENDS


def test_capacity_starves_a_ready_task_without_calling_it_predecessor_blocked() -> None:
    result = capacity_bottleneck()
    assert result.category == PARTIAL
    assert result.where_shown.startswith("deal_A:A1 stays at 0")
    assert "utilization is 1" in result.why_shown
    assert result.mutation_accepted is False


def test_information_and_cross_organization_are_gaps() -> None:
    by_id = {result.scenario_id: result for result in all_results()}
    assert by_id["information"].category == GAP
    assert by_id["cross_organization"].category == GAP
    assert by_id["authority"].category == AMBIGUOUS
    assert by_id["authority"].mutation_accepted is False
    assert by_id["authority"].epistemic_status == "HYPOTHESIS"


def test_negative_controls_reject_the_mutation() -> None:
    negatives = [result for result in all_results() if result.scenario_id.startswith("negative_")]
    assert len(negatives) == 3
    for result in negatives:
        assert result.category == AMBIGUOUS
        assert result.ambiguity is True
        assert result.mutation_accepted is False
        assert result.epistemic_status == "HYPOTHESIS"


def test_macro_relations_do_not_name_a_deal_or_task_and_micro_fingerprint_holds() -> None:
    for source, target in RELATION_ENDS.values():
        assert "Deal" not in source and "Deal" not in target
        assert "Task" not in source and "Task" not in target
    assert tuple(field.name for field in fields(Task)) == ("task_id", "deal_id", "task_type", "name")
    assert "information" not in {field.name for field in fields(TaskOccurrence)}
    assert fingerprint() is True
