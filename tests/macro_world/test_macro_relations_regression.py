"""Phase 2 does not move the frozen micro model or the Phase 1 result."""

from dataclasses import fields
from pathlib import Path

from dealos.domain.models import Task, TaskOccurrence
from dealos.macro_world.experiments.run_macro_world import VALIDATED, execute
from dealos.macro_world.relations.experiments.run_macro_relations import execute as execute_relations

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "dealos" / "macro_world" / "relations"
FORBIDDEN = (
    "dealos.sim",
    "dealos.policies",
    "dealos.generator",
    "dealos.domain",
    "dealos.org",
    "dealos.analysis",
    "dealos.problem_evolution",
)


def test_phase1_still_validates() -> None:
    _results, line = execute(0)
    assert line == VALIDATED


def test_live_micro_fields_stay_unchanged() -> None:
    assert tuple(field.name for field in fields(Task)) == ("task_id", "deal_id", "task_type", "name")
    assert tuple(field.name for field in fields(TaskOccurrence)) == (
        "occurrence_id",
        "deal_id",
        "task_id",
        "lifecycle",
        "progress",
        "offer_id",
        "readiness_source",
    )


def test_the_relation_package_does_not_import_the_frozen_core_and_the_graph_stays_macro() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.rglob("*.py"))
    for name in FORBIDDEN:
        assert name not in text
    _assessed, line = execute_relations(0)
    assert line == "FIVE HIDDEN FACTS RECOVERABLE WHEN THEIR OWN FIELDS ARE EXPOSED"
    for _scenario, evaluation, failures in _assessed:
        if failures:
            continue
        for name in (evaluation.source_entity, evaluation.target_entity):
            assert "Task" not in name
            assert "Deal" not in name
