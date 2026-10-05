"""The macro graph keeps only committed macro-to-macro edges."""

from __future__ import annotations

from dataclasses import dataclass

from dealos.macro_world.relations.models import BRIDGE, RELATION_ENDS
from dealos.macro_world.relations.validate import RelationEvaluation


@dataclass(frozen=True)
class GraphEdge:
    relation_name: str
    source_entity: str
    target_entity: str
    epistemic_status: str


def graph_edges(rows: tuple[tuple[RelationEvaluation, tuple[str, ...]], ...]) -> tuple[GraphEdge, ...]:
    edges: list[GraphEdge] = []
    seen: set[str] = set()
    for evaluation, failures in rows:
        if failures or not _include(evaluation) or evaluation.relation_name in seen:
            continue
        source, target = RELATION_ENDS[evaluation.relation_name]
        if source in BRIDGE or target in BRIDGE:
            continue
        seen.add(evaluation.relation_name)
        edges.append(GraphEdge(evaluation.relation_name, source, target, evaluation.epistemic_status))
    return tuple(edges)


def _include(evaluation: RelationEvaluation) -> bool:
    return (
        evaluation.mutation_accepted
        and evaluation.ground_truth_present
        and not evaluation.ambiguity
        and         evaluation.epistemic_status == "FACT"
    )
