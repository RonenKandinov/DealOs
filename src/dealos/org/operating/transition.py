"""O_(t+1) = F(O_t, E_t). Each event is explicit. Nothing is inferred."""

from __future__ import annotations

from dataclasses import dataclass, replace

from dealos.org.operating.entities import (
    Accountability,
    Capability,
    Decision,
    DecisionRight,
    Delegation,
    Escalation,
    InformationObject,
    Person,
    Relation,
    Resource,
    Veto,
)
from dealos.org.operating.state import OrgState, integrity_errors


class TransitionError(ValueError):
    pass


@dataclass(frozen=True)
class Allocate:
    pool_id: str
    amount: float
    holder_id: str


@dataclass(frozen=True)
class Release:
    pool_id: str
    amount: float


@dataclass(frozen=True)
class MoveResource:
    resource_id: str
    to_role_id: str


@dataclass(frozen=True)
class ProduceInformation:
    information_id: str
    system_id: str


@dataclass(frozen=True)
class ConsumeInformation:
    information_id: str


@dataclass(frozen=True)
class ReceiveExternalInformation:
    external_relation_id: str


@dataclass(frozen=True)
class OpenDecision:
    decision_id: str
    action: str


@dataclass(frozen=True)
class Approve:
    decision_id: str
    actor_id: str


@dataclass(frozen=True)
class Reject:
    decision_id: str
    actor_id: str


@dataclass(frozen=True)
class Delegate:
    delegation_id: str
    from_holder_id: str
    to_holder_id: str
    decision_id: str


@dataclass(frozen=True)
class IssueVeto:
    veto_id: str
    holder_id: str
    decision_id: str


@dataclass(frozen=True)
class Escalate:
    escalation_id: str
    rule_id: str
    subject_id: str


@dataclass(frozen=True)
class Tick:
    time: int


@dataclass(frozen=True)
class AssignRole:
    person_id: str
    role_id: str


@dataclass(frozen=True)
class AssignCapability:
    holder_id: str
    capability_id: str


@dataclass(frozen=True)
class AssignAccountability:
    accountability_id: str
    holder_id: str
    statement: str


@dataclass(frozen=True)
class GrantDecisionRight:
    right_id: str
    holder_id: str
    decision_id: str
    kind: str


@dataclass(frozen=True)
class Participate:
    """A resource appears on an activity. This event adds no authority and no handoff."""

    resource_id: str
    activity: str


def apply(state: OrgState, event: object) -> OrgState:
    nxt = _clone(state)
    kind = type(event)
    if kind is Allocate:
        _allocate(nxt, event)
    elif kind is Release:
        _release(nxt, event)
    elif kind is MoveResource:
        _move(nxt, event)
    elif kind is ProduceInformation:
        _produce(nxt, event)
    elif kind is ConsumeInformation:
        _consume(nxt, event)
    elif kind is ReceiveExternalInformation:
        _receive(nxt, event)
    elif kind is OpenDecision:
        nxt.decisions[event.decision_id] = Decision(event.decision_id, event.action, "open")
    elif kind is Approve:
        _decide(nxt, event.decision_id, event.actor_id, "approved")
    elif kind is Reject:
        _decide(nxt, event.decision_id, event.actor_id, "rejected")
    elif kind is Delegate:
        _delegate(nxt, event)
    elif kind is IssueVeto:
        nxt.vetoes[event.veto_id] = Veto(event.veto_id, event.holder_id, event.decision_id, True)
    elif kind is Escalate:
        _escalate(nxt, event)
    elif kind is Tick:
        _tick(nxt, event)
    elif kind is Participate:
        if event.resource_id not in nxt.resources:
            nxt.resources[event.resource_id] = Resource(event.resource_id)
    elif kind is AssignRole:
        _assign_role(nxt, event)
    elif kind is AssignCapability:
        _assign_capability(nxt, event)
    elif kind is AssignAccountability:
        nxt.accountabilities[event.accountability_id] = Accountability(
            event.accountability_id, event.holder_id, event.statement
        )
        nxt.relations[event.accountability_id] = Relation(
            event.accountability_id, "accountable_for", event.holder_id, event.statement
        )
    elif kind is GrantDecisionRight:
        nxt.decision_rights[event.right_id] = DecisionRight(
            event.right_id, event.holder_id, event.decision_id, event.kind
        )
        nxt.relations[event.right_id] = Relation(event.right_id, event.kind, event.holder_id, event.decision_id)
    else:
        raise TransitionError(f"unknown event {kind}")
    errors = integrity_errors(nxt)
    if errors:
        raise TransitionError("; ".join(errors))
    return nxt


def authority_eligible(state: OrgState, decision_id: str, actor_id: str) -> bool:
    if any(veto.active and veto.decision_id == decision_id for veto in state.vetoes.values()):
        return False
    granted = any(
        grant.decision_id == decision_id and grant.holder_id == actor_id for grant in state.authority.values()
    )
    delegated = any(
        item.active and item.decision_id == decision_id and item.to_holder_id == actor_id
        for item in state.delegations.values()
    )
    return granted or delegated


def _clone(state: OrgState) -> OrgState:
    return replace(
        state,
        organizations=dict(state.organizations),
        business_units=dict(state.business_units),
        departments=dict(state.departments),
        teams=dict(state.teams),
        people=dict(state.people),
        roles=dict(state.roles),
        capabilities=dict(state.capabilities),
        resources=dict(state.resources),
        capacity={key: replace(pool) for key, pool in state.capacity.items()},
        responsibilities=dict(state.responsibilities),
        accountabilities=dict(state.accountabilities),
        decisions={key: replace(item) for key, item in state.decisions.items()},
        decision_rights=dict(state.decision_rights),
        authority=dict(state.authority),
        delegations={key: replace(item) for key, item in state.delegations.items()},
        vetoes={key: replace(item) for key, item in state.vetoes.items()},
        information={key: replace(item) for key, item in state.information.items()},
        governance=dict(state.governance),
        escalation_rules=dict(state.escalation_rules),
        escalations=dict(state.escalations),
        slas={key: replace(item) for key, item in state.slas.items()},
        processes=dict(state.processes),
        systems=dict(state.systems),
        external_relations=dict(state.external_relations),
        relations=dict(state.relations),
        constraints=dict(state.constraints),
    )


def _allocate(state: OrgState, event: Allocate) -> None:
    pool = state.capacity[event.pool_id]
    if event.amount < 0 or event.amount > pool.available + 1e-9:
        raise TransitionError("allocation exceeds available capacity")
    state.capacity[event.pool_id] = replace(pool, available=pool.available - event.amount)
    state.relations[f"hold:{event.pool_id}:{event.holder_id}"] = Relation(
        f"hold:{event.pool_id}:{event.holder_id}",
        "holds_capacity",
        event.holder_id,
        event.pool_id,
    )


def _release(state: OrgState, event: Release) -> None:
    pool = state.capacity[event.pool_id]
    room = pool.total - pool.available
    state.capacity[event.pool_id] = replace(pool, available=pool.available + min(event.amount, room))


def _move(state: OrgState, event: MoveResource) -> None:
    if event.to_role_id not in state.roles:
        raise TransitionError("move target role is unknown")
    state.relations[f"role-of:{event.resource_id}"] = Relation(
        f"role-of:{event.resource_id}",
        "resource_role",
        event.resource_id,
        event.to_role_id,
    )


def _produce(state: OrgState, event: ProduceInformation) -> None:
    if event.system_id not in state.systems:
        raise TransitionError("producer system is unknown")
    current = state.information.get(event.information_id, InformationObject(event.information_id, False))
    state.information[event.information_id] = replace(current, available=True)
    state.relations[f"produces:{event.system_id}:{event.information_id}"] = Relation(
        f"produces:{event.system_id}:{event.information_id}",
        "produces",
        event.system_id,
        event.information_id,
    )


def _consume(state: OrgState, event: ConsumeInformation) -> None:
    info = state.information[event.information_id]
    if not info.available:
        raise TransitionError("information is unavailable")
    state.information[event.information_id] = replace(info, available=False)


def _receive(state: OrgState, event: ReceiveExternalInformation) -> None:
    link = state.external_relations[event.external_relation_id]
    info = state.information[link.information_id]
    state.information[link.information_id] = replace(info, available=True)


def _decide(state: OrgState, decision_id: str, actor_id: str, status: str) -> None:
    if any(veto.active and veto.decision_id == decision_id for veto in state.vetoes.values()):
        raise TransitionError("veto blocks the decision")
    if not _holder_or_delegate(state, decision_id, actor_id):
        rule = next((item for item in state.escalation_rules.values() if item.condition == "authority_unavailable"), None)
        if rule is None:
            raise TransitionError("actor is not eligible")
        state.escalations[f"esc:{decision_id}"] = Escalation(f"esc:{decision_id}", rule.rule_id, decision_id, True)
        state.decisions[decision_id] = replace(state.decisions[decision_id], status="escalated")
        return
    state.decisions[decision_id] = replace(state.decisions[decision_id], status=status)


def authority_eligible(state: OrgState, decision_id: str, actor_id: str) -> bool:
    if any(veto.active and veto.decision_id == decision_id for veto in state.vetoes.values()):
        return False
    return _holder_or_delegate(state, decision_id, actor_id)


def _holder_or_delegate(state: OrgState, decision_id: str, actor_id: str) -> bool:
    granted = any(
        grant.decision_id == decision_id and grant.holder_id == actor_id for grant in state.authority.values()
    )
    delegated = any(
        item.active and item.decision_id == decision_id and item.to_holder_id == actor_id
        for item in state.delegations.values()
    )
    return granted or delegated


def _delegate(state: OrgState, event: Delegate) -> None:
    state.delegations[event.delegation_id] = Delegation(
        event.delegation_id,
        event.from_holder_id,
        event.to_holder_id,
        event.decision_id,
        True,
    )
    state.relations[event.delegation_id] = Relation(
        event.delegation_id,
        "delegates",
        event.from_holder_id,
        event.to_holder_id,
    )


def _escalate(state: OrgState, event) -> None:
    if event.rule_id not in state.escalation_rules:
        raise TransitionError("escalation rule is unknown")
    state.escalations[event.escalation_id] = Escalation(event.escalation_id, event.rule_id, event.subject_id, True)


def _assign_role(state: OrgState, event: AssignRole) -> None:
    if event.person_id not in state.people:
        state.people[event.person_id] = Person(event.person_id)
    if event.role_id not in state.roles:
        raise TransitionError("role is unknown")
    state.relations[f"holds:{event.person_id}:{event.role_id}"] = Relation(
        f"holds:{event.person_id}:{event.role_id}",
        "holds_role",
        event.person_id,
        event.role_id,
    )


def _assign_capability(state: OrgState, event: AssignCapability) -> None:
    if event.capability_id not in state.capabilities:
        state.capabilities[event.capability_id] = Capability(event.capability_id, event.capability_id)
    state.relations[f"can:{event.holder_id}:{event.capability_id}"] = Relation(
        f"can:{event.holder_id}:{event.capability_id}",
        "has_capability",
        event.holder_id,
        event.capability_id,
    )


def _tick(state: OrgState, event: Tick) -> None:
    state.time = event.time
    for sla_id, sla in list(state.slas.items()):
        subject = state.decisions.get(sla.subject_id)
        still_open = subject is None or subject.status == "open"
        if event.time >= sla.deadline and still_open:
            state.slas[sla_id] = replace(sla, breached=True)
            rule = next((item for item in state.escalation_rules.values() if item.condition == "sla_breached"), None)
            if rule is not None:
                state.escalations[f"sla:{sla_id}"] = Escalation(f"sla:{sla_id}", rule.rule_id, sla.subject_id, True)
