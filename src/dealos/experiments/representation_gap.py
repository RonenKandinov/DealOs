"""Classify a missing observation, a missing representation, and an unsupported story.

The current Macro gate is read as it stands. No primitive is installed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from dealos.diagnostics.manual_scenario import chain_debug_scenario
from dealos.domain.graph import predecessors
from dealos.domain.models import AllocationAction
from dealos.domain.readiness import AndMinReadiness
from dealos.experiments.macro_micro_integration import comparison_rows, invariant_failures, run_all
from dealos.experiments.macro_micro_multiconstraint import CONSTRAINT, TASK, TASK_NAME, organizational_state
from dealos.org.operating.bridge import CAN_PROGRESS, diagnose
from dealos.org.operating.state import OrgState
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1
from dealos.sim.env import SalesEnvironment

OBSERVATION_GAP = "observation_gap"
REPRESENTATION_GAP = "representation_gap"
SEMANTIC_GAP = "semantic_gap"
NO_GAP = "no_gap"

BARE_SLOT = "UnmodeledConstraint"


@dataclass(frozen=True)
class Observation:
    """A supplied record. None means that field was not observed."""

    task_ready: bool | None = None
    capacity_available: bool | None = None
    required_information_available: bool | None = None
    external_information_available: bool | None = None
    authority_available: bool | None = None
    veto: bool | None = None
    observed_progress: float | None = None


@dataclass(frozen=True)
class Proposal:
    """A candidate primitive. A semantic assumption is part of the proposal, not derived."""

    name: str
    semantic_assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class GapRow:
    scenario: str
    observations_available: bool
    current_model_prediction: str
    observed_outcome: str
    classification: str
    candidate: str
    accepted: bool


def satisfied_state() -> OrgState:
    """Every field the current TaskConstraint can name holds."""

    return organizational_state(capacity=1.0, profile=True, external=True, grant=True, veto=False)


def observations_available(observation: Observation) -> bool:
    values = (
        observation.task_ready,
        observation.capacity_available,
        observation.required_information_available,
        observation.external_information_available,
        observation.authority_available,
        observation.veto,
        observation.observed_progress,
    )
    return all(value is not None for value in values)


def adds_unsupported_semantics(proposal: Proposal) -> bool:
    """A proposal that explains the outcome, or names anything other than a bare slot, adds semantics."""

    if proposal.semantic_assumptions:
        return True
    return proposal.name != BARE_SLOT


def candidate_accepted(proposal: Proposal | None) -> bool:
    """Acceptance rejects unsupported semantics. It does not make the primitive true."""

    if proposal is None:
        return False
    return not adds_unsupported_semantics(proposal)


def classify(prediction: str, observation: Observation, proposal: Proposal | None = None) -> str:
    """Three gap labels, plus no_gap when the current model already matches the outcome."""

    if not observations_available(observation):
        return OBSERVATION_GAP
    if proposal is not None and adds_unsupported_semantics(proposal):
        return SEMANTIC_GAP
    if _matches(prediction, observation.observed_progress):
        return NO_GAP
    return REPRESENTATION_GAP


def run_all_gaps() -> tuple[GapRow, ...]:
    prediction = diagnose(satisfied_state(), CONSTRAINT).reason
    hidden = Observation(
        task_ready=True,
        capacity_available=True,
        required_information_available=True,
        external_information_available=True,
        authority_available=True,
        veto=False,
        observed_progress=None,
    )
    contradicted = Observation(
        task_ready=True,
        capacity_available=True,
        required_information_available=True,
        external_information_available=True,
        authority_available=True,
        veto=False,
        observed_progress=0.0,
    )
    explained = Observation(
        task_ready=True,
        capacity_available=True,
        required_information_available=True,
        external_information_available=True,
        authority_available=True,
        veto=False,
        observed_progress=_explained_progress(),
    )
    slot = Proposal(BARE_SLOT)
    story = Proposal("TimeGapIsWaiting", ("time_gap_is_waiting",))
    specs = (
        ("hidden_causal_observation", hidden, None),
        ("unexplained_non_progress", contradicted, slot),
        ("unsupported_causal_story", contradicted, story),
        ("explained_progress", explained, None),
    )
    return tuple(_row(name, prediction, observation, proposal) for name, observation, proposal in specs)


def integration_still_passes() -> bool:
    return invariant_failures() == () and all(row.passed for row in run_all() + comparison_rows())


def write_report(root: Path) -> str:
    rows = run_all_gaps()
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "representation_gap_experiment.csv", rows)
    text = _render(rows)
    (docs / "representation_gap_experiment.md").write_text(text, encoding="utf-8")
    return text


def _row(scenario: str, prediction: str, observation: Observation, proposal: Proposal | None) -> GapRow:
    available = observations_available(observation)
    if observation.observed_progress is None:
        outcome = "hidden"
    else:
        outcome = f"{observation.observed_progress}"
    return GapRow(
        scenario,
        available,
        prediction,
        outcome,
        classify(prediction, observation, proposal),
        "" if proposal is None else proposal.name,
        candidate_accepted(proposal),
    )


def _matches(prediction: str, observed_progress: float | None) -> bool:
    if observed_progress is None:
        return False
    progressed = observed_progress > 0.0
    if prediction == CAN_PROGRESS:
        return progressed
    return not progressed


def _explained_progress() -> float:
    env = SalesEnvironment(chain_debug_scenario())
    micro = env.reset()
    occurrence = micro.primary_occurrence[TASK]
    env.step(AllocationAction({("deal_A", occurrence, "ae"): 1.0}))
    return env.get_state().task_progress[TASK]


def _micro() -> tuple[float, float, bool]:
    env = SalesEnvironment(chain_debug_scenario())
    micro = env.reset()
    deal = env.scenario.deals["deal_A"]
    readiness = AndMinReadiness().readiness(
        [micro.task_progress[("deal_A", pred)] for pred in predecessors(deal.edges, TASK_NAME)]
    )
    return micro.task_progress[TASK], readiness, TASK in micro.blocked_tasks


def _render(rows: tuple[GapRow, ...]) -> str:
    progress, readiness, blocked = _micro()
    diagnosis = diagnose(satisfied_state(), CONSTRAINT)
    fingerprint = baseline_one_occurrence_matches_v1()
    integration = integration_still_passes()
    lines = [
        "# Representation-gap experiment",
        "",
        "## Question",
        "",
        "When deal_A:A1 is Micro-ready and every configured TaskConstraint holds, the current diagnosis is can_progress. If a recorded outcome still says the task did not progress, which kind of gap is that?",
        "",
        "The classifier has three gap labels. `no_gap` means none of the three applies.",
        "",
        "- `observation_gap`: a field required to compare the prediction with the outcome was not supplied.",
        "- `representation_gap`: those fields were supplied, and the current TaskConstraint has no remaining failure that can express an explanation.",
        "- `semantic_gap`: a proposal explains the outcome by a semantic assumption the operating model does not support.",
        "",
        "## Fixed Micro task and satisfied Macro state",
        "",
        f"Task `{TASK_NAME}`. Micro readiness {readiness}. Progress before any allocation {progress}. In blocked_tasks: {blocked}.",
        f"Diagnosis reason `{diagnosis.reason}`. Blocking reasons: {len(diagnosis.blocking_reasons)}.",
        "Capacity is available, `profile` is available, `external_profile` is available, an AuthorityGrant is present, and no veto is active. Those are the fields TaskConstraint can name.",
        "",
        "## Results",
        "",
        "| scenario | observations_available | current_model_prediction | observed_outcome | classification | candidate | accepted |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.scenario} | {row.observations_available} | {row.current_model_prediction} | "
            f"{row.observed_outcome} | {row.classification} | {row.candidate or 'none'} | {row.accepted} |"
        )
    lines.extend(
        [
            "",
            "## Scenarios",
            "",
            "Hidden causal observation. The constraint flags are filled and `observed_progress` is withheld. The label is observation_gap. The same prediction is not called a representation gap while the outcome is missing.",
            "",
            "Complete current observations. `observed_progress` is the supplied value 0. The diagnosis remains can_progress because no configured constraint fails. The label is representation_gap. No cause is assigned to that 0.",
            "",
            "The candidate on that row is UnmodeledConstraint: a named slot with an empty assumption list. The validator accepts that slot because it does not state a cause. Acceptance here means the proposal was not rejected for unsupported semantics. The slot is not installed, and acceptance is not evidence that the slot is the true cause.",
            "",
            "Unsupported causal story. The same complete record is paired with a proposal whose assumption is `time_gap_is_waiting`. A time gap is not waiting in the operating model. The label is semantic_gap and the candidate is rejected.",
            "",
            "Explained progress. The gate is can_progress, so the existing allocation step runs. The recorded progress is that step's result. The prediction matches it. The label is no_gap.",
            "",
            "## Checks that stayed in place",
            "",
            f"Macro-Micro integration rows and invariants still pass: {integration}.",
            f"Seed-0 FIFO fingerprint, 2 completed deals in 40 steps: {fingerprint}.",
            "",
            "## What the experiment demonstrates",
            "",
            "A missing outcome, a complete outcome the current constraint fields cannot explain, and a proposal that adds an unsupported meaning receive three different labels. A matching outcome receives no gap label.",
            "",
            "## What it does not demonstrate",
            "",
            "It does not identify why the supplied progress was 0. It does not show that UnmodeledConstraint is a real organizational fact. It does not install that slot, and it does not change Micro readiness, the progress formula, policies, BPI17 analysis, or the existing organizational primitives.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_csv(path: Path, rows: tuple[GapRow, ...]) -> None:
    fields = (
        "scenario",
        "observations_available",
        "current_model_prediction",
        "observed_outcome",
        "classification",
        "candidate",
        "accepted",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: getattr(row, name) for name in fields})


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    print(write_report(root))


if __name__ == "__main__":
    main()
