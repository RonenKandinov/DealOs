"""The macro graph records every checked relation with its epistemic fields kept apart."""

from __future__ import annotations

from dataclasses import dataclass

from dealos.macro_world.relations.models import BRIDGE, FACT, HYPOTHESIS, INFERENCE
from dealos.macro_world.relations.validate import RelationEvaluation

RECOVERABLE = "RECOVERABLE"
HIDDEN = "HIDDEN"
UNKNOWN = "UNKNOWN"
INFERENCE_EDGE = "inference"
AMBIGUOUS = "ambiguous"
REJECTED = "rejected"
RECOVERABLE_EDGE = "recoverable"


@dataclass(frozen=True)
class GraphEdge:
    scenario_id: str
    relation_name: str
    source_entity: str
    target_entity: str
    epistemic_status: str
    ground_truth_present: bool
    recoverability: str
    ambiguity: bool
    representable: bool
    mutation_accepted: bool
    disposition: str


def recoverability_label(evaluation: RelationEvaluation) -> str:
    if evaluation.ambiguity or evaluation.epistemic_status in {HYPOTHESIS, INFERENCE} or not evaluation.ground_truth_present:
        return UNKNOWN
    if evaluation.recoverable and evaluation.epistemic_status == FACT:
        return RECOVERABLE
    if evaluation.epistemic_status == FACT and not evaluation.recoverable:
        return HIDDEN
    return UNKNOWN


def disposition(evaluation: RelationEvaluation) -> str:
    """Separate ground truth, recovery, ambiguity, inference, and rejection."""

    if evaluation.epistemic_status == INFERENCE:
        return INFERENCE_EDGE
    if not evaluation.ground_truth_present:
        return REJECTED
    if evaluation.ambiguity:
        return AMBIGUOUS
    if evaluation.recoverable and evaluation.representable_after:
        return RECOVERABLE_EDGE
    if evaluation.representable_after and evaluation.epistemic_status == FACT:
        return "hidden"
    return REJECTED


def graph_edges(rows: tuple[tuple[RelationEvaluation, tuple[str, ...]], ...]) -> tuple[GraphEdge, ...]:
    edges: list[GraphEdge] = []
    for evaluation, failures in rows:
        if failures:
            continue
        if evaluation.source_entity in BRIDGE or evaluation.target_entity in BRIDGE:
            continue
        edges.append(
            GraphEdge(
                evaluation.scenario_id,
                evaluation.relation_name,
                evaluation.source_entity,
                evaluation.target_entity,
                evaluation.epistemic_status,
                evaluation.ground_truth_present,
                recoverability_label(evaluation),
                evaluation.ambiguity,
                evaluation.representable_after,
                evaluation.mutation_accepted,
                disposition(evaluation),
            )
        )
    return tuple(edges)
