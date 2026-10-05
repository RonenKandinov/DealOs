"""Evaluation vectors. Capabilities stay separate from a single score."""

from __future__ import annotations

from dataclasses import dataclass

from dealos.macro_world.models import HYPOTHESIS, Representation
from dealos.macro_world.queries import REQUIREMENTS, representable
from dealos.macro_world.scenarios import Scenario

CAPABILITIES = tuple(REQUIREMENTS)


@dataclass(frozen=True)
class EvaluationVector:
    scenario_id: str
    capabilities_before: tuple[tuple[str, bool], ...]
    capabilities_after: tuple[tuple[str, bool], ...]
    mismatches_resolved: tuple[str, ...]
    mismatches_partial: tuple[str, ...]
    mismatches_unresolved: tuple[str, ...]
    ground_truth_coverage: float
    observation_faithfulness: float
    regression: bool
    complexity_delta: int
    epistemic_violations: int


def evaluate(
    scenario: Scenario,
    candidate: Representation,
    leak_count: int,
    epistemic_violations: int,
) -> EvaluationVector:
    before = _flags(scenario.initial)
    after = _flags(candidate)
    mismatch_id = scenario.mismatch.mismatch_id
    if scenario.epistemic_status == HYPOTHESIS or not scenario.accept_mutation:
        resolved: tuple[str, ...] = ()
        partial: tuple[str, ...] = ()
        unresolved = (mismatch_id,)
    elif representable(candidate, scenario.capability) and not representable(scenario.initial, scenario.capability):
        resolved = (mismatch_id,)
        partial = ()
        unresolved = ()
    else:
        resolved = ()
        partial = (mismatch_id,)
        unresolved = ()
    if scenario.capability == "ambiguous_interpretation":
        coverage = 0.0
    else:
        coverage = 1.0 if representable(candidate, scenario.capability) else 0.0
    regression = not scenario.initial.primitives <= candidate.primitives
    return EvaluationVector(
        scenario.scenario_id,
        before,
        after,
        resolved,
        partial,
        unresolved,
        coverage,
        1.0 if leak_count == 0 else 0.0,
        regression,
        len(candidate.primitives) - len(scenario.initial.primitives),
        epistemic_violations,
    )


def _flags(representation: Representation) -> tuple[tuple[str, bool], ...]:
    return tuple((name, representable(representation, name)) for name in CAPABILITIES)
