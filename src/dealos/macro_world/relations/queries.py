"""Representable, recoverable, and interpretable questions, answered by the relation spec."""

from __future__ import annotations

from collections.abc import Mapping

from dealos.macro_world.models import Representation
from dealos.macro_world.relations.models import (
    RELATION_SPECS,
    MacroWorld,
    RelationMask,
    RelationObservation,
    RelationSpec,
    relation_spec,
)


def representable(
    representation: Representation,
    relation_name: str,
    specs: Mapping[str, RelationSpec] | None = None,
) -> bool:
    return relation_spec(relation_name, specs).primitives <= representation.primitives


def evidence_present(
    observations: tuple[RelationObservation, ...],
    mask: RelationMask,
    relation_name: str,
    specs: Mapping[str, RelationSpec] | None = None,
) -> bool:
    return relation_spec(relation_name, specs).evidence_rule(observations, mask)


def interpretable(
    observations: tuple[RelationObservation, ...],
    mask: RelationMask,
    relation_name: str,
    specs: Mapping[str, RelationSpec] | None = None,
) -> bool:
    return relation_spec(relation_name, specs).interpretation_rule(observations, mask)


def recoverable(
    observations: tuple[RelationObservation, ...],
    mask: RelationMask,
    relation_name: str,
    specs: Mapping[str, RelationSpec] | None = None,
) -> bool:
    """A relation is recoverable only when its own evidence and its own interpretation both hold."""

    spec = relation_spec(relation_name, specs)
    return spec.evidence_rule(observations, mask) and spec.interpretation_rule(observations, mask)


def gt_has(world: MacroWorld, relation_name: str) -> bool:
    return any(relation.name == relation_name for relation in world.relations)


def activity_is_not_a_role(observations: tuple[RelationObservation, ...]) -> bool:
    blocked = {"LegalReviewer", "SecurityReviewer", "FinanceApprover", "Legal", "Security"}
    return all(observation.get("activity") not in blocked for observation in observations)


def known_specs() -> Mapping[str, RelationSpec]:
    return RELATION_SPECS
