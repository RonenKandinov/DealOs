"""Macro organization record around the frozen micro deal model.

The micro model remains G_D: tasks, AND dependencies, progress, readiness,
suitability, capacity, and allocation. This module does not read or write
that state and does not implement a decision function.

A record here can name systems, roles, actors, discrete authority, information
links, resource-control rights, and the bridge from a deal task type to those
objects. Every statement carries an epistemic label. Candidate department
names are data a caller may store. This module loads none of them.

Company evolution is outside this record. There is no reporting hierarchy,
because seniority is not authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


LAYER = "macro"


class Epistemic(Enum):
    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"


class Side(Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class AuthorityState(Enum):
    """Discrete authority. A number in [0, 1] is not a member of this set."""

    NONE = "none"
    INFORM = "inform"
    RECOMMEND = "recommend"
    PROPOSE = "propose"
    EXECUTE = "execute"
    APPROVE = "approve"
    OVERRIDE = "override"


class ResourceRight(Enum):
    """A right over an existing micro resource id. It does not change C_r."""

    REQUEST = "request"
    ALLOCATE = "allocate"
    REALLOCATE = "reallocate"
    OVERRIDE = "override"


class InvolvementChange(Enum):
    ENTER = "enter"
    LEAVE = "leave"


class InvolvementReason(Enum):
    TASK_READY = "task_ready"
    ESCALATION = "escalation"
    EXTERNAL = "external"
    OTHER = "other"
    UNKNOWN = "unknown"


class OrganizationRecordError(ValueError):
    def __init__(self, messages: list[str]) -> None:
        self.messages = list(messages)
        super().__init__("; ".join(self.messages))


@dataclass(frozen=True)
class OrgSystem:
    """One organizational system S_k. State kinds are names, not live values."""

    system_id: str
    domain: str
    input_kinds: frozenset[str]
    state_kinds: frozenset[str]
    decision_kinds: frozenset[str]
    action_kinds: frozenset[str]
    output_kinds: frozenset[str]
    status: Epistemic


@dataclass(frozen=True)
class Role:
    role_id: str
    system_id: str
    status: Epistemic


@dataclass(frozen=True)
class Actor:
    actor_id: str
    side: Side
    role_ids: frozenset[str]
    status: Epistemic


@dataclass(frozen=True)
class AuthorityGrant:
    """Authority(role, decision, context) as one discrete state.

    An empty context is the default grant. A non-empty context applies only
    when a record contains that grant. Grants are not derived from rank.
    """

    role_id: str
    decision_kind: str
    context: frozenset[str]
    state: AuthorityState
    status: Epistemic


@dataclass(frozen=True)
class InformationLink:
    """Output of one system consumed as input by another. Not an authority grant."""

    producer_system_id: str
    info_kind: str
    consumer_system_id: str
    visible_to: frozenset[str]
    status: Epistemic


@dataclass(frozen=True)
class ResourceControl:
    """Who may request, allocate, reallocate, or override an existing resource id."""

    resource_id: str
    role_id: str
    right: ResourceRight
    status: Epistemic


@dataclass(frozen=True)
class DealTaskBinding:
    """Bridge from a micro task type to macro system, roles, and information.

    An empty approving role means this binding claims no approval.
    Readiness of the micro task is not a field here.
    """

    task_type: str
    system_id: str
    executing_role_id: str
    required_info: frozenset[str]
    status: Epistemic
    task_name: str = ""
    approving_role_id: str = ""
    decision_kind: str = ""


@dataclass(frozen=True)
class EscalationRule:
    """A decision moves from one role to another when the condition tokens hold."""

    decision_kind: str
    condition: frozenset[str]
    from_role_id: str
    to_role_id: str
    status: Epistemic


@dataclass(frozen=True)
class InvolvementEvent:
    """A role enters or leaves one deal. This does not change the company."""

    deal_id: str
    time_label: str
    role_id: str
    change: InvolvementChange
    reason: InvolvementReason
    status: Epistemic


@dataclass(frozen=True)
class OrganizationRecord:
    """OrganizationTemplate as data. Scale band is a label, not a second model."""

    name: str
    systems: tuple[OrgSystem, ...] = ()
    roles: tuple[Role, ...] = ()
    actors: tuple[Actor, ...] = ()
    grants: tuple[AuthorityGrant, ...] = ()
    links: tuple[InformationLink, ...] = ()
    controls: tuple[ResourceControl, ...] = ()
    bindings: tuple[DealTaskBinding, ...] = ()
    escalations: tuple[EscalationRule, ...] = ()
    involvement: tuple[InvolvementEvent, ...] = ()
    scale_band: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "systems", tuple(self.systems))
        object.__setattr__(self, "roles", tuple(self.roles))
        object.__setattr__(self, "actors", tuple(self.actors))
        object.__setattr__(self, "grants", tuple(self.grants))
        object.__setattr__(self, "links", tuple(self.links))
        object.__setattr__(self, "controls", tuple(self.controls))
        object.__setattr__(self, "bindings", tuple(self.bindings))
        object.__setattr__(self, "escalations", tuple(self.escalations))
        object.__setattr__(self, "involvement", tuple(self.involvement))
        errors = structure_errors(self)
        if errors:
            raise OrganizationRecordError(errors)


@dataclass(frozen=True)
class BindingAccount:
    """Read-only account of one bridge. It does not diagnose a problem class."""

    binding: DealTaskBinding
    distinct_approver: bool
    executor_grants: tuple[AuthorityGrant, ...]
    approver_grants: tuple[AuthorityGrant, ...]
    missing_info: tuple[str, ...]
    escalation_rules: tuple[EscalationRule, ...]


def structure_errors(record: OrganizationRecord) -> list[str]:
    """Structural checks. They do not compare the record with a micro scenario."""

    errors: list[str] = []
    if not record.name.strip():
        errors.append("organization name is empty")
    systems = _index(record.systems, "system_id", "system", errors)
    roles = _index(record.roles, "role_id", "role", errors)
    _index(record.actors, "actor_id", "actor", errors)
    for system in record.systems:
        _tokens(system.system_id, "system id", errors)
        _tokens(system.domain, "system domain", errors)
        _kind_set(system.input_kinds, f"system {system.system_id} inputs", errors)
        _kind_set(system.state_kinds, f"system {system.system_id} state kinds", errors)
        _kind_set(system.decision_kinds, f"system {system.system_id} decisions", errors)
        _kind_set(system.action_kinds, f"system {system.system_id} actions", errors)
        _kind_set(system.output_kinds, f"system {system.system_id} outputs", errors)
    for role in record.roles:
        _tokens(role.role_id, "role id", errors)
        if role.system_id not in systems:
            errors.append(f"role {role.role_id} names unknown system {role.system_id}")
    for actor in record.actors:
        _tokens(actor.actor_id, "actor id", errors)
        for role_id in actor.role_ids:
            if role_id not in roles:
                errors.append(f"actor {actor.actor_id} names unknown role {role_id}")
    seen_grants: set[tuple[str, str, frozenset[str]]] = set()
    for grant in record.grants:
        key = (grant.role_id, grant.decision_kind, grant.context)
        if key in seen_grants:
            errors.append(f"duplicate authority grant {grant.role_id} {grant.decision_kind}")
        seen_grants.add(key)
        role = roles.get(grant.role_id)
        if role is None:
            errors.append(f"authority grant names unknown role {grant.role_id}")
            continue
        system = systems.get(role.system_id)
        if system is None or grant.decision_kind not in system.decision_kinds:
            errors.append(
                f"decision {grant.decision_kind} is not declared by the system of role {grant.role_id}"
            )
        _kind_set(grant.context, f"authority context for {grant.role_id}", errors)
    for link in record.links:
        producer = systems.get(link.producer_system_id)
        consumer = systems.get(link.consumer_system_id)
        if producer is None:
            errors.append(f"information link names unknown producer {link.producer_system_id}")
        elif link.info_kind not in producer.output_kinds:
            errors.append(
                f"information {link.info_kind} is not an output of {link.producer_system_id}"
            )
        if consumer is None:
            errors.append(f"information link names unknown consumer {link.consumer_system_id}")
        elif link.info_kind not in consumer.input_kinds:
            errors.append(
                f"information {link.info_kind} is not an input of {link.consumer_system_id}"
            )
        for role_id in link.visible_to:
            if role_id not in roles:
                errors.append(f"information link visible_to names unknown role {role_id}")
    seen_controls: set[tuple[str, str, ResourceRight]] = set()
    for control in record.controls:
        key = (control.resource_id, control.role_id, control.right)
        if key in seen_controls:
            errors.append(f"duplicate resource control {control.resource_id} {control.role_id}")
        seen_controls.add(key)
        _tokens(control.resource_id, "resource id", errors)
        if control.role_id not in roles:
            errors.append(f"resource control names unknown role {control.role_id}")
    for binding in record.bindings:
        _tokens(binding.task_type, "task type", errors)
        system = systems.get(binding.system_id)
        if system is None:
            errors.append(f"binding for {binding.task_type} names unknown system {binding.system_id}")
            system_inputs: frozenset[str] = frozenset()
            system_decisions: frozenset[str] = frozenset()
        else:
            system_inputs = system.input_kinds
            system_decisions = system.decision_kinds
        executor = roles.get(binding.executing_role_id)
        if executor is None:
            errors.append(f"binding for {binding.task_type} names unknown executing role")
        elif system is not None and executor.system_id != binding.system_id:
            errors.append(
                f"executing role {binding.executing_role_id} is outside system {binding.system_id}"
            )
        if binding.approving_role_id:
            if binding.approving_role_id not in roles:
                errors.append(f"binding for {binding.task_type} names unknown approving role")
            if not binding.decision_kind:
                errors.append(f"binding for {binding.task_type} has an approver and no decision")
        if binding.decision_kind and binding.decision_kind not in system_decisions:
            errors.append(
                f"binding decision {binding.decision_kind} is not declared by {binding.system_id}"
            )
        for kind in binding.required_info:
            if kind not in system_inputs:
                errors.append(f"required information {kind} is not an input of {binding.system_id}")
    for rule in record.escalations:
        if not rule.condition:
            errors.append(f"escalation of {rule.decision_kind} has an empty condition")
        else:
            _kind_set(rule.condition, f"escalation condition for {rule.decision_kind}", errors)
        if rule.from_role_id == rule.to_role_id:
            errors.append(f"escalation of {rule.decision_kind} stays on the same role")
        source = roles.get(rule.from_role_id)
        if source is None:
            errors.append(f"escalation names unknown role {rule.from_role_id}")
        else:
            system = systems.get(source.system_id)
            if system is None or rule.decision_kind not in system.decision_kinds:
                errors.append(
                    f"escalated decision {rule.decision_kind} is not declared for {rule.from_role_id}"
                )
        if rule.to_role_id not in roles:
            errors.append(f"escalation names unknown role {rule.to_role_id}")
    for event in record.involvement:
        _tokens(event.deal_id, "involvement deal id", errors)
        _tokens(event.time_label, "involvement time label", errors)
        if event.role_id not in roles:
            errors.append(f"involvement names unknown role {event.role_id}")
    return errors


def check_against_micro(
    record: OrganizationRecord,
    *,
    resource_ids: frozenset[str],
    task_types: frozenset[str],
) -> None:
    """Compare bridge identifiers with a micro scenario's ids. Does not step the deal."""

    errors: list[str] = []
    for control in record.controls:
        if control.resource_id not in resource_ids:
            errors.append(f"resource control {control.resource_id} is not a micro resource")
    for binding in record.bindings:
        if binding.task_type not in task_types:
            errors.append(f"binding task type {binding.task_type} is not a micro task type")
    if errors:
        raise OrganizationRecordError(errors)


def describe_binding(record: OrganizationRecord, binding: DealTaskBinding) -> BindingAccount:
    """Report the macro objects attached to one bridge. Does not read deal progress."""

    if binding not in record.bindings:
        raise OrganizationRecordError([f"binding for {binding.task_type} is not in the record"])
    supplied = {
        link.info_kind
        for link in record.links
        if link.consumer_system_id == binding.system_id
    }
    missing = tuple(sorted(kind for kind in binding.required_info if kind not in supplied))
    return BindingAccount(
        binding=binding,
        distinct_approver=bool(binding.approving_role_id)
        and binding.approving_role_id != binding.executing_role_id,
        executor_grants=_grants_for(record, binding.executing_role_id, binding.decision_kind),
        approver_grants=_grants_for(record, binding.approving_role_id, binding.decision_kind),
        missing_info=missing,
        escalation_rules=tuple(
            rule
            for rule in record.escalations
            if rule.decision_kind == binding.decision_kind
            and rule.from_role_id in {binding.executing_role_id, binding.approving_role_id}
        ),
    )


def _grants_for(
    record: OrganizationRecord,
    role_id: str,
    decision_kind: str,
) -> tuple[AuthorityGrant, ...]:
    if not role_id or not decision_kind:
        return ()
    return tuple(
        grant
        for grant in record.grants
        if grant.role_id == role_id and grant.decision_kind == decision_kind
    )


def _index(items: tuple, field: str, label: str, errors: list[str]) -> dict[str, object]:
    found: dict[str, object] = {}
    for item in items:
        key = getattr(item, field)
        if key in found:
            errors.append(f"duplicate {label} {key}")
        found[key] = item
    return found


def _tokens(value: str, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} is empty")


def _kind_set(values: frozenset[str], label: str, errors: list[str]) -> None:
    for value in values:
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} contains an empty token")
