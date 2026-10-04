"""Inspectable dataclasses for deals, resources, actions, and portfolio state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from dealos.domain.graph import CycleError, require_dag


class TaskStatus(Enum):
    """Observable task status. Derived from progress and readiness, never stored as the source of truth."""

    NOT_STARTED = "not_started"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class OccurrenceLifecycle(Enum):
    """Execution state of one task occurrence. Resume is suspended → active, not a stored value."""

    SCHEDULED = "scheduled"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    ABORTED = "aborted"
    WITHDRAWN = "withdrawn"


class ReadinessSource(Enum):
    """Where an occurrence's readiness comes from.

    type_and_min is the existing predecessor rule on the type DAG.
    unresolved means no occurrence-level predecessor rule has been supplied.
    declared is a fixture statement, not a causal inference.
    """

    TYPE_AND_MIN = "type_and_min"
    UNRESOLVED = "unresolved"
    DECLARED = "declared"


def primary_occurrence_id(deal_id: str, task_id: str) -> str:
    return f"{deal_id}:{task_id}#1"


def task_of_occurrence(deal_id: str, occurrence_id: str) -> str:
    """Recover the task id stored in `{deal_id}:{task_id}#{n}`."""

    prefix = f"{deal_id}:"
    if not occurrence_id.startswith(prefix) or "#" not in occurrence_id:
        raise ValueError(f"occurrence id {occurrence_id} is not in deal {deal_id}")
    body, _number = occurrence_id.rsplit("#", 1)
    return body[len(prefix) :]


@dataclass(frozen=True)
class SimulationConfig:
    """Assumptions the simulator applies on every step.

    These are configuration, not hidden constants inside the update rule.
    """

    completion_tolerance: float = 1e-9
    blocked_readiness_threshold: float = 0.0
    capacity_tolerance: float = 1e-9


@dataclass(frozen=True)
class GeneratorConfig:
    """Controls synthetic portfolios. Presets differ only by these fields."""

    name: str
    n_deals: int
    horizon: int
    capacities: Mapping[str, float]
    extra_edge_probability: float
    optional_drop_probability: float
    partial_start_fraction: float
    phi_range: tuple[float, float]
    alpha_range: tuple[float, float]
    q_range: tuple[float, float]
    protected_task_types: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.n_deals < 1:
            raise ValueError("n_deals must be at least 1")
        if self.horizon < 0:
            raise ValueError("horizon must be non-negative")
        object.__setattr__(self, "capacities", MappingProxyType(dict(self.capacities)))
        object.__setattr__(self, "protected_task_types", frozenset(self.protected_task_types))


@dataclass(frozen=True)
class Task:
    task_id: str
    deal_id: str
    task_type: str
    name: str


@dataclass(frozen=True)
class TaskOccurrence:
    """One execution of a task type. The type stays a vertex of the deal DAG.

    Extra occurrences do not replace the type-level progress used by readiness.
    offer_id is set only when a caller has a real OfferID. It is not required.
    """

    occurrence_id: str
    deal_id: str
    task_id: str
    lifecycle: OccurrenceLifecycle
    progress: float
    offer_id: str | None = None
    readiness_source: ReadinessSource = ReadinessSource.TYPE_AND_MIN

    def __post_init__(self) -> None:
        if not self.occurrence_id or not self.deal_id or not self.task_id:
            raise ValueError("occurrence identity is empty")
        if not 0.0 <= self.progress <= 1.0:
            raise ValueError(f"occurrence progress {self.progress} is outside [0, 1]")


@dataclass(frozen=True)
class Offer:
    """An offer object identified by OfferID. It does not own workflow occurrences."""

    offer_id: str
    case_id: str

    def __post_init__(self) -> None:
        if not self.offer_id.strip():
            raise ValueError("offer id is empty")
        if not self.case_id:
            raise ValueError("offer case id is empty")


@dataclass(frozen=True)
class DealGraph:
    """One deal as a directed AND-dependency graph G_i = (V_i, E_i)."""

    deal_id: str
    tasks: Mapping[str, Task]
    edges: frozenset[tuple[str, str]]
    targets: frozenset[str]

    def __post_init__(self) -> None:
        tasks = dict(self.tasks)
        edges = frozenset(self.edges)
        targets = frozenset(self.targets)
        object.__setattr__(self, "tasks", MappingProxyType(tasks))
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "targets", targets)
        if not tasks:
            raise ValueError(f"deal {self.deal_id} has no tasks")
        if not targets:
            raise ValueError(f"deal {self.deal_id} has no target tasks")
        for task_id, task in tasks.items():
            if task.task_id != task_id or task.deal_id != self.deal_id:
                raise ValueError(f"task identity mismatch in deal {self.deal_id}")
        for source, dest in edges:
            if source not in tasks or dest not in tasks:
                raise ValueError(f"edge {(source, dest)} is not inside deal {self.deal_id}")
            if source == dest:
                raise CycleError(f"self-loop on {source}")
        missing = targets - set(tasks)
        if missing:
            raise ValueError(f"unknown target tasks {sorted(missing)}")
        require_dag(set(tasks), edges)


@dataclass(frozen=True)
class Resource:
    """Organizational capacity of one resource type. C_r is constant in V1."""

    resource_id: str
    resource_type: str
    capacity: float

    def __post_init__(self) -> None:
        if self.capacity < 0:
            raise ValueError(f"capacity of {self.resource_id} must be non-negative")


@dataclass
class AllocationAction:
    """Fractional allocation in [0, 1], keyed by (deal_id, occurrence_id, resource_id)."""

    allocations: dict[tuple[str, str, str], float]

    def get(self, deal_id: str, occurrence_id: str, resource_id: str) -> float:
        return self.allocations.get((deal_id, occurrence_id, resource_id), 0.0)

    def used_by_resource(self) -> dict[str, float]:
        used: dict[str, float] = {}
        for (_, _, resource_id), amount in self.allocations.items():
            used[resource_id] = used.get(resource_id, 0.0) + amount
        return used


@dataclass
class PortfolioState:
    """Dynamic state S_t. Static graphs and parameters live on Scenario."""

    time: int
    task_progress: dict[tuple[str, str], float]
    task_status: dict[tuple[str, str], TaskStatus]
    capacities: dict[str, float]
    allocations: dict[tuple[str, str, str], float]
    completed_deals: set[str]
    blocked_tasks: set[tuple[str, str]]
    ready_since: dict[tuple[str, str], int | None]
    task_completed_at: dict[tuple[str, str], int | None]
    deal_completed_at: dict[str, int | None]
    deal_complete: dict[str, int]
    occurrences: dict[str, TaskOccurrence] = field(default_factory=dict)
    offers: dict[str, Offer] = field(default_factory=dict)
    primary_occurrence: dict[tuple[str, str], str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "time": self.time,
            "task_progress": {
                f"{deal_id}:{task_id}": value
                for (deal_id, task_id), value in sorted(self.task_progress.items())
            },
            "task_status": {
                f"{deal_id}:{task_id}": status.value
                for (deal_id, task_id), status in sorted(self.task_status.items())
            },
            "capacities": dict(sorted(self.capacities.items())),
            "allocations": {
                f"{deal_id}:{task_id}:{resource_id}": value
                for (deal_id, task_id, resource_id), value in sorted(self.allocations.items())
            },
            "completed_deals": sorted(self.completed_deals),
            "blocked_tasks": [f"{deal_id}:{task_id}" for deal_id, task_id in sorted(self.blocked_tasks)],
            "ready_since": {
                f"{deal_id}:{task_id}": value
                for (deal_id, task_id), value in sorted(self.ready_since.items())
            },
            "task_completed_at": {
                f"{deal_id}:{task_id}": value
                for (deal_id, task_id), value in sorted(self.task_completed_at.items())
            },
            "deal_completed_at": dict(sorted(self.deal_completed_at.items())),
            "deal_complete": dict(sorted(self.deal_complete.items())),
            "occurrences": [
                {
                    "occurrence_id": occurrence.occurrence_id,
                    "deal_id": occurrence.deal_id,
                    "task_id": occurrence.task_id,
                    "lifecycle": occurrence.lifecycle.value,
                    "progress": occurrence.progress,
                    "offer_id": occurrence.offer_id,
                    "readiness_source": occurrence.readiness_source.value,
                }
                for occurrence in (
                    self.occurrences[key] for key in sorted(self.occurrences)
                )
            ],
            "offers": [
                {"offer_id": offer.offer_id, "case_id": offer.case_id}
                for offer in (self.offers[key] for key in sorted(self.offers))
            ],
            "primary_occurrence": {
                f"{deal_id}:{task_id}": occurrence_id
                for (deal_id, task_id), occurrence_id in sorted(self.primary_occurrence.items())
            },
        }


@dataclass(frozen=True)
class Scenario:
    """Static scenario parameters. Progress and allocations are not stored here."""

    seed: int
    simulation: SimulationConfig
    generator: GeneratorConfig
    deals: Mapping[str, DealGraph]
    resources: Mapping[str, Resource]
    phi: Mapping[tuple[str, str], float]
    alpha: Mapping[tuple[str, str, str], float]
    suitability: Mapping[tuple[str, str, str], float]
    initial_progress: Mapping[tuple[str, str], float]
    horizon: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "deals", MappingProxyType(dict(self.deals)))
        object.__setattr__(self, "resources", MappingProxyType(dict(self.resources)))
        object.__setattr__(self, "phi", MappingProxyType(dict(self.phi)))
        object.__setattr__(self, "alpha", MappingProxyType(dict(self.alpha)))
        object.__setattr__(self, "suitability", MappingProxyType(dict(self.suitability)))
        object.__setattr__(self, "initial_progress", MappingProxyType(dict(self.initial_progress)))

    def task_keys(self) -> list[tuple[str, str]]:
        keys: list[tuple[str, str]] = []
        for deal_id in sorted(self.deals):
            for task_id in sorted(self.deals[deal_id].tasks):
                keys.append((deal_id, task_id))
        return keys

    def to_dict(self) -> dict[str, object]:
        deals: dict[str, object] = {}
        for deal_id, deal in sorted(self.deals.items()):
            deals[deal_id] = {
                "tasks": [
                    {
                        "task_id": task.task_id,
                        "task_type": task.task_type,
                        "name": task.name,
                        "phi": self.phi[(deal_id, task.task_id)],
                        "initial_progress": self.initial_progress[(deal_id, task.task_id)],
                    }
                    for task in (self.deals[deal_id].tasks[task_id] for task_id in sorted(deal.tasks))
                ],
                "edges": [list(edge) for edge in sorted(deal.edges)],
                "targets": sorted(deal.targets),
            }
        return {
            "seed": self.seed,
            "horizon": self.horizon,
            "preset": self.generator.name,
            "resources": {
                resource_id: {
                    "resource_type": resource.resource_type,
                    "capacity": resource.capacity,
                }
                for resource_id, resource in sorted(self.resources.items())
            },
            "deals": deals,
            "simulation": {
                "completion_tolerance": self.simulation.completion_tolerance,
                "blocked_readiness_threshold": self.simulation.blocked_readiness_threshold,
                "capacity_tolerance": self.simulation.capacity_tolerance,
            },
            "parameters": {
                f"{deal_id}:{task_id}:{resource_id}": {
                    "alpha": self.alpha[(deal_id, task_id, resource_id)],
                    "q": self.suitability[(deal_id, task_id, resource_id)],
                }
                for deal_id, task_id in self.task_keys()
                for resource_id in sorted(self.resources)
            },
        }
