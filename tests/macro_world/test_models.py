"""Ground-truth records stay separate from the frozen simulator classes."""

from dataclasses import fields
from pathlib import Path

from dealos.domain.models import Task, TaskOccurrence
from dealos.macro_world.generator import reference_world
from dealos.macro_world.ground_truth import integrity_errors
from dealos.macro_world.models import (
    FORBIDDEN_IMPLICIT,
    R0_EXTRA,
    R_MICRO,
    GroundTruth,
    Mutation,
    Resource,
    micro_representation,
    r0_representation,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "dealos" / "macro_world"
FORBIDDEN = (
    "dealos.sim",
    "dealos.policies",
    "dealos.generator",
    "dealos.domain",
    "dealos.org",
    "dealos.analysis",
    "dealos.problem_evolution",
)


def test_reference_world_relations_point_at_stored_objects() -> None:
    assert integrity_errors(reference_world()) == ()


def test_a_resource_role_must_exist() -> None:
    world = reference_world()
    broken = GroundTruth(organization=world.organization, resources=(Resource("R17", "missing", "org_resource"),))
    errors = integrity_errors(broken)
    assert any("unknown role" in error for error in errors)


def test_live_task_fields_stay_unchanged() -> None:
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


def test_r0_adds_only_the_justified_resource_primitives() -> None:
    assert r0_representation().primitives == R_MICRO | R0_EXTRA
    assert FORBIDDEN_IMPLICIT.isdisjoint(r0_representation().primitives)


def test_adding_a_primitive_returns_a_new_representation() -> None:
    parent = micro_representation()
    child = parent.with_primitives(("Role",), "R1")
    assert parent.primitives == R_MICRO
    assert child.primitives == R_MICRO | {"Role"}
    assert Mutation("AddObject", "Role").target == "Role"


def test_package_does_not_import_the_frozen_core() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.rglob("*.py"))
    for name in FORBIDDEN:
        assert name not in text
