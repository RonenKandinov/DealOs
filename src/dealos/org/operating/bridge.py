"""Macro constraints on a ready micro task. The simulator formula is not edited."""

from __future__ import annotations

from dataclasses import dataclass

from dealos.org.operating.entities import TaskConstraint
from dealos.org.operating.state import OrgState


CAN_PROGRESS = "can_progress"
NOT_READY = "not_ready"
CAPACITY_UNAVAILABLE = "capacity_unavailable"
INFORMATION_UNAVAILABLE = "information_unavailable"
AUTHORITY_UNAVAILABLE = "authority_unavailable"
VETO = "veto"
EXTERNAL_INFORMATION_UNAVAILABLE = "external_information_unavailable"


@dataclass(frozen=True)
class Blocker:
    """One constraint that the current organizational state fails."""

    reason: str
    evidence: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Diagnosis:
    task_id: str
    ready: bool
    reason: str
    evidence: tuple[tuple[str, str], ...] = ()
    blocking_reasons: tuple[Blocker, ...] = ()


def diagnose(state: OrgState, constraint: TaskConstraint) -> Diagnosis:
    """A ready task progresses only when every configured macro requirement holds.

    ``reason`` stays the first failure in the historical order. ``blocking_reasons``
    lists every failure present in the current state.
    """

    evidence = _evidence(state, constraint)
    blockers = _blockers(state, constraint)
    reason = blockers[0].reason if blockers else CAN_PROGRESS
    return Diagnosis(constraint.task_id, constraint.ready, reason, evidence, tuple(blockers))


def _blockers(state: OrgState, constraint: TaskConstraint) -> list[Blocker]:
    found: list[Blocker] = []
    if not constraint.ready:
        found.append(Blocker(NOT_READY, (("task_id", constraint.task_id), ("ready", "False"))))
    if constraint.capacity_pool_id is not None:
        pool = state.capacity[constraint.capacity_pool_id]
        if pool.available <= 1e-9:
            found.append(
                Blocker(
                    CAPACITY_UNAVAILABLE,
                    (
                        ("pool_id", pool.pool_id),
                        ("available", f"{pool.available}"),
                        ("required", "1"),
                    ),
                )
            )
    if constraint.external_relation_id is not None:
        link = state.external_relations[constraint.external_relation_id]
        info = state.information[link.information_id]
        if not info.available:
            found.append(
                Blocker(
                    EXTERNAL_INFORMATION_UNAVAILABLE,
                    (
                        ("external_relation_id", link.relation_id),
                        ("information_id", info.information_id),
                        ("available", "False"),
                        ("external_kind", link.kind),
                        ("external_context", link.context_id),
                    ),
                )
            )
    if constraint.information_id is not None and not state.information[constraint.information_id].available:
        info = state.information[constraint.information_id]
        found.append(
            Blocker(
                INFORMATION_UNAVAILABLE,
                (("information_id", info.information_id), ("available", "False")),
            )
        )
    if constraint.decision_id is not None:
        vetoes = [
            item.veto_id
            for item in state.vetoes.values()
            if item.active and item.decision_id == constraint.decision_id
        ]
        if vetoes:
            found.append(
                Blocker(
                    VETO,
                    (("decision_id", constraint.decision_id), ("active_vetoes", ",".join(vetoes))),
                )
            )
        holders = [grant.holder_id for grant in state.authority.values() if grant.decision_id == constraint.decision_id]
        delegates = [
            item.to_holder_id
            for item in state.delegations.values()
            if item.active and item.decision_id == constraint.decision_id
        ]
        if not holders and not delegates:
            found.append(
                Blocker(
                    AUTHORITY_UNAVAILABLE,
                    (("decision_id", constraint.decision_id), ("authority_holders", "")),
                )
            )
    return found


def _evidence(state: OrgState, constraint: TaskConstraint) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = [("task_id", constraint.task_id), ("ready", str(constraint.ready))]
    if constraint.capacity_pool_id is not None:
        pool = state.capacity[constraint.capacity_pool_id]
        rows.extend(
            [
                ("pool_id", pool.pool_id),
                ("available", f"{pool.available}"),
                ("required", "1"),
            ]
        )
    if constraint.information_id is not None:
        info = state.information[constraint.information_id]
        rows.extend([("information_id", info.information_id), ("available_information", str(info.available))])
    if constraint.external_relation_id is not None:
        link = state.external_relations[constraint.external_relation_id]
        info = state.information[link.information_id]
        rows.extend(
            [
                ("external_relation_id", link.relation_id),
                ("external_kind", link.kind),
                ("external_context", link.context_id),
                ("information_id", info.information_id),
                ("available_information", str(info.available)),
            ]
        )
    if constraint.decision_id is not None:
        rows.append(("decision_id", constraint.decision_id))
        holders = [grant.holder_id for grant in state.authority.values() if grant.decision_id == constraint.decision_id]
        rows.append(("authority_holders", ",".join(holders)))
        vetoes = [item.veto_id for item in state.vetoes.values() if item.active and item.decision_id == constraint.decision_id]
        rows.append(("active_vetoes", ",".join(vetoes)))
    return tuple(rows)
