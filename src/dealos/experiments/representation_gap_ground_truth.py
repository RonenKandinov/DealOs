"""A hidden rule in the world, absent from the gate. Candidates fit on three worlds and are scored on others.

Ground truth, observation, projected organizational state, prediction, and candidate evaluation
are separate functions. Nothing here is installed in the operating model.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path

from dealos.diagnostics.manual_scenario import chain_debug_scenario
from dealos.domain.models import AllocationAction
from dealos.experiments.representation_gap import (
    Observation,
    Proposal,
    classify,
    integration_still_passes,
)
from dealos.org.operating.bridge import CAN_PROGRESS, diagnose
from dealos.org.operating.entities import (
    AuthorityGrant,
    CapacityPool,
    Decision,
    ExternalRelation,
    InformationObject,
    Organization,
    System,
    TaskConstraint,
)
from dealos.org.operating.state import OrgState
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1
from dealos.sim.env import SalesEnvironment

TASK = ("deal_A", "deal_A:A1")
TASK_NAME = "deal_A:A1"
PROGRESS = "progress"
BLOCKED = "blocked"

HIDDEN_PRIMITIVE = "DutyExclusion"
HIDDEN_FIELDS = frozenset({"required_clear", "active", HIDDEN_PRIMITIVE})
PUBLIC_FIELDS = frozenset(
    {
        "task_ready",
        "capacity_available",
        "required_information_available",
        "external_information_available",
        "authority_available",
        "veto",
        "observed_progress",
        "decision_id",
        "eligible_holders",
        "prior_actor_id",
    }
)

PROPOSAL_IDS = ("G1", "G2", "G3")
HOLDOUT_IDS = ("G4", "G5", "G6")
NAMED_IDS = PROPOSAL_IDS + HOLDOUT_IDS
PRIOR = "Alice"
OTHERS = ("Bob", "Carol", "Dan")
THRESHOLDS = (1, 2, 3)
SEARCH_LIST = ("UnmodeledConstraint", "DutyExclusion", "DecisionQuorum", "TimeGapIsWaiting")
GRID_DECISIONS = (("approve_deal", 1), ("approve_budget", 2), ("approve_contract", 3))


@dataclass(frozen=True)
class DutyExclusion:
    """Ground-truth rule. The operating model has no field for it."""

    decision_id: str
    prior_actor_id: str
    required_clear: int
    active: bool = True


@dataclass(frozen=True)
class World:
    scenario_id: str
    split: str
    decision_id: str
    holders: tuple[str, ...]
    prior_actor_id: str
    rule: DutyExclusion | None


@dataclass(frozen=True)
class PublicRow:
    """What an observer sees. Hidden fields are not here."""

    scenario_id: str
    decision_id: str
    eligible_holders: tuple[str, ...]
    prior_actor_id: str
    observation: Observation

    def fields(self) -> dict[str, str]:
        values = {
            "task_ready": str(self.observation.task_ready),
            "capacity_available": str(self.observation.capacity_available),
            "required_information_available": str(self.observation.required_information_available),
            "external_information_available": str(self.observation.external_information_available),
            "authority_available": str(self.observation.authority_available),
            "veto": str(self.observation.veto),
            "observed_progress": str(self.observation.observed_progress),
            "decision_id": self.decision_id,
            "eligible_holders": "|".join(self.eligible_holders),
            "prior_actor_id": self.prior_actor_id,
        }
        return values


@dataclass(frozen=True)
class Candidate:
    """A candidate representation. thresholds is one integer per decision id."""

    name: str
    thresholds: tuple[tuple[str, int], ...] = ()
    semantic_assumptions: tuple[str, ...] = ()
    attributes: tuple[str, ...] = ()
    fitted: bool = True

    def proposal(self) -> Proposal:
        return Proposal(self.name, self.semantic_assumptions)


@dataclass(frozen=True)
class WorldResult:
    world: World
    row: PublicRow
    current_model_prediction: str
    ground_truth_outcome: str
    mismatch: bool
    classification: str


@dataclass(frozen=True)
class CandidateVector:
    name: str
    admissible: bool
    fitted: bool
    proposal_matches: int
    holdout_matches: int
    coverage: int
    contradiction_resolution: bool
    regression: bool
    specificity: bool
    semantic_safety: bool
    complexity: int
    supported: bool
    grid_correct: int
    grid_total: int
    grid_failures: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class GapRow:
    scenario_id: str
    split: str
    ground_truth_hidden_primitive: str
    ground_truth_parameters: str
    observation_fields: str
    current_model_prediction: str
    ground_truth_outcome: str
    mismatch: bool
    classification: str
    candidate: str
    candidate_prediction: str
    candidate_correct: bool
    admissible: bool
    supported: bool
    regression: bool
    semantic_safety: bool
    complexity: int


def make_world(
    scenario_id: str,
    split: str,
    decision_id: str,
    holders: tuple[str, ...],
    *,
    required_clear: int | None,
    active: bool = True,
    prior_actor_id: str = PRIOR,
) -> World:
    rule = None if required_clear is None else DutyExclusion(decision_id, prior_actor_id, required_clear, active)
    return World(scenario_id, split, decision_id, holders, prior_actor_id, rule)


def named_worlds() -> tuple[World, ...]:
    return (
        make_world("G1", "proposal", "approve_deal", ("Alice",), required_clear=1),
        make_world("G2", "proposal", "approve_deal", ("Alice", "Bob"), required_clear=1),
        make_world("G3", "proposal", "approve_budget", ("Alice", "Bob"), required_clear=2),
        make_world("G4", "holdout", "approve_budget", ("Alice", "Bob", "Carol"), required_clear=2),
        make_world("G5", "holdout", "approve_deal", ("Alice", "Bob", "Carol"), required_clear=1, active=False),
        make_world("G6", "holdout", "file_report", ("Alice",), required_clear=None),
    )


def grid_worlds() -> tuple[World, ...]:
    worlds: list[World] = []
    for decision_id, required_clear in GRID_DECISIONS:
        for clear in range(4):
            for prior_in in (True, False):
                for active in (True, False):
                    holders = ((PRIOR,) if prior_in else ()) + OTHERS[:clear]
                    scenario_id = f"X-{decision_id}-c{clear}-{'p' if prior_in else 'n'}-{'a' if active else 'i'}"
                    worlds.append(
                        make_world(
                            scenario_id,
                            "grid",
                            decision_id,
                            holders,
                            required_clear=required_clear,
                            active=active,
                        )
                    )
    return tuple(worlds)


def project_org(world: World) -> OrgState:
    """The current representation. Every field it can hold is copied; the rule has no field."""

    state = OrgState()
    state.organizations["seller"] = Organization("seller")
    state.organizations["buyer"] = Organization("buyer", external=True)
    state.capacity["pool"] = CapacityPool("pool", 1.0, 1.0)
    state.information["profile"] = InformationObject("profile", True)
    state.information["external_profile"] = InformationObject("external_profile", True)
    state.systems["crm"] = System("crm", "seller")
    state.decisions[world.decision_id] = Decision(world.decision_id, world.decision_id, "open")
    state.external_relations["buyer_profile"] = ExternalRelation(
        "buyer_profile", "buyer", "seller", "external_profile", kind="configured", context_id="deal_A"
    )
    for holder in world.holders:
        state.authority[f"grant:{holder}"] = AuthorityGrant(f"grant:{holder}", holder, "role", world.decision_id)
    return state


def constraint_for(world: World) -> TaskConstraint:
    return TaskConstraint(
        TASK_NAME,
        capacity_pool_id="pool",
        information_id="profile",
        decision_id=world.decision_id,
        external_relation_id="buyer_profile",
        ready=True,
    )


def current_prediction(world: World) -> str:
    return diagnose(project_org(world), constraint_for(world)).reason


def clear_holders(world: World) -> tuple[str, ...]:
    return tuple(holder for holder in world.holders if holder != world.prior_actor_id)


def ground_truth_outcome(world: World) -> str:
    """The world's own rule decides. The gate decides when the rule is absent or inactive."""

    if current_prediction(world) != CAN_PROGRESS:
        return BLOCKED
    if world.rule is None or not world.rule.active:
        return PROGRESS
    return PROGRESS if len(clear_holders(world)) >= world.rule.required_clear else BLOCKED


def project_observation(world: World, outcome: str) -> PublicRow:
    state = project_org(world)
    diagnosis = diagnose(state, constraint_for(world))
    reasons = {blocker.reason for blocker in diagnosis.blocking_reasons}
    observation = Observation(
        task_ready=True,
        capacity_available="capacity_unavailable" not in reasons,
        required_information_available="information_unavailable" not in reasons,
        external_information_available="external_information_unavailable" not in reasons,
        authority_available="authority_unavailable" not in reasons,
        veto="veto" in reasons,
        observed_progress=_step() if outcome == PROGRESS else 0.0,
    )
    return PublicRow(world.scenario_id, world.decision_id, world.holders, world.prior_actor_id, observation)


def world_result(world: World) -> WorldResult:
    prediction = current_prediction(world)
    outcome = ground_truth_outcome(world)
    row = project_observation(world, outcome)
    mismatch = (prediction == CAN_PROGRESS) != (outcome == PROGRESS)
    return WorldResult(world, row, prediction, outcome, mismatch, classify(prediction, row.observation))


def world_results(worlds: tuple[World, ...] | None = None) -> tuple[WorldResult, ...]:
    return tuple(world_result(world) for world in (worlds or named_worlds()))


def propose(rows: tuple[PublicRow, ...]) -> tuple[Candidate, ...]:
    """Fit each family in the search list on public rows. Smallest consistent threshold per decision."""

    found: list[Candidate] = [Candidate("UnmodeledConstraint")]
    for family, attributes in (("DutyExclusion", ("prior_actor_id", "threshold")), ("DecisionQuorum", ("threshold",))):
        thresholds: list[tuple[str, int]] = []
        fitted = True
        for decision_id in sorted({row.decision_id for row in rows}):
            subset = [row for row in rows if row.decision_id == decision_id]
            consistent = [n for n in THRESHOLDS if all(_consistent(family, row, n) for row in subset)]
            if not consistent:
                fitted = False
                break
            thresholds.append((decision_id, consistent[0]))
        found.append(Candidate(family, tuple(thresholds), (), attributes, fitted))
    found.append(Candidate("TimeGapIsWaiting", (), ("time_gap_is_waiting",), ("time_gap",), False))
    return tuple(found)


def predict(candidate: Candidate, row: PublicRow, gate: str) -> str:
    if gate != CAN_PROGRESS:
        return BLOCKED
    count = _count(candidate.name, row)
    thresholds = dict(candidate.thresholds)
    if count is None or row.decision_id not in thresholds:
        return PROGRESS
    return PROGRESS if count >= thresholds[row.decision_id] else BLOCKED


def admissible(candidate: Candidate) -> bool:
    return not candidate.semantic_assumptions and candidate.name in SEARCH_LIST


def evaluate(
    candidate: Candidate,
    named: tuple[WorldResult, ...],
    grid: tuple[WorldResult, ...],
    integration_ok: bool,
) -> CandidateVector:
    by_id = {result.world.scenario_id: result for result in named}
    correct = {sid: predict(candidate, by_id[sid].row, by_id[sid].current_model_prediction) == by_id[sid].ground_truth_outcome for sid in NAMED_IDS}
    proposal_matches = sum(correct[sid] for sid in PROPOSAL_IDS)
    holdout_matches = sum(correct[sid] for sid in HOLDOUT_IDS)
    contradictions = [sid for sid in NAMED_IDS if by_id[sid].mismatch]
    resolution = bool(contradictions) and all(correct[sid] for sid in contradictions)
    controls = [sid for sid in HOLDOUT_IDS if not by_id[sid].mismatch]
    regression = integration_ok and all(correct[sid] for sid in controls)
    specificity = all(
        predict(candidate, by_id[sid].row, by_id[sid].current_model_prediction) == PROGRESS for sid in ("G5", "G6")
    )
    safe = not candidate.semantic_assumptions
    ok = admissible(candidate)
    supported = ok and candidate.fitted and proposal_matches == len(PROPOSAL_IDS) and holdout_matches == len(HOLDOUT_IDS)
    failures: dict[str, int] = {}
    grid_correct = 0
    for result in grid:
        if predict(candidate, result.row, result.current_model_prediction) == result.ground_truth_outcome:
            grid_correct += 1
        else:
            key = _failure_category(candidate, result.world)
            failures[key] = failures.get(key, 0) + 1
    return CandidateVector(
        candidate.name,
        ok,
        candidate.fitted,
        proposal_matches,
        holdout_matches,
        sum(correct.values()),
        resolution,
        regression,
        specificity,
        safe,
        len(candidate.attributes),
        supported,
        grid_correct,
        len(grid),
        tuple(sorted(failures.items())),
    )


def run_experiment() -> tuple[tuple[WorldResult, ...], tuple[WorldResult, ...], tuple[Candidate, ...], tuple[CandidateVector, ...]]:
    named = world_results()
    grid = world_results(grid_worlds())
    proposal_rows = tuple(result.row for result in named if result.world.scenario_id in PROPOSAL_IDS)
    candidates = propose(proposal_rows)
    integration_ok = integration_still_passes()
    vectors = tuple(evaluate(candidate, named, grid, integration_ok) for candidate in candidates)
    return named, grid, candidates, vectors


def gap_rows(named: tuple[WorldResult, ...], candidates: tuple[Candidate, ...], vectors: tuple[CandidateVector, ...]) -> tuple[GapRow, ...]:
    by_name = {vector.name: vector for vector in vectors}
    rows: list[GapRow] = []
    for result in named:
        for candidate in candidates:
            vector = by_name[candidate.name]
            prediction = predict(candidate, result.row, result.current_model_prediction)
            rows.append(
                GapRow(
                    result.world.scenario_id,
                    result.world.split,
                    HIDDEN_PRIMITIVE if result.world.rule is not None else "none",
                    _parameters(result.world),
                    ";".join(f"{key}={value}" for key, value in result.row.fields().items()),
                    result.current_model_prediction,
                    result.ground_truth_outcome,
                    result.mismatch,
                    result.classification,
                    candidate.name,
                    prediction,
                    prediction == result.ground_truth_outcome,
                    vector.admissible,
                    vector.supported,
                    vector.regression,
                    vector.semantic_safety,
                    vector.complexity,
                )
            )
    return tuple(rows)


def write_report(root: Path) -> str:
    named, grid, candidates, vectors = run_experiment()
    rows = gap_rows(named, candidates, vectors)
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "representation_gap_ground_truth.csv", rows)
    text = _render(named, grid, candidates, vectors)
    (docs / "representation_gap_ground_truth_experiment.md").write_text(text, encoding="utf-8")
    return text


def _consistent(family: str, row: PublicRow, threshold: int) -> bool:
    progressed = (row.observation.observed_progress or 0.0) > 0.0
    count = _count(family, row)
    return count is not None and (count >= threshold) == progressed


def _count(family: str, row: PublicRow) -> int | None:
    if family == "DutyExclusion":
        return len([holder for holder in row.eligible_holders if holder != row.prior_actor_id])
    if family == "DecisionQuorum":
        return len(row.eligible_holders)
    return None


def _failure_category(candidate: Candidate, world: World) -> str:
    if world.decision_id not in dict(candidate.thresholds):
        return "unseen_decision"
    if world.rule is None or not world.rule.active:
        return "inactive_rule"
    if world.prior_actor_id not in world.holders:
        return "prior_not_holder"
    return "other"


def _grid_split(candidate: Candidate, baseline: Candidate, grid: tuple[WorldResult, ...]) -> tuple[int, int]:
    gained = 0
    lost = 0
    for result in grid:
        mine = predict(candidate, result.row, result.current_model_prediction) == result.ground_truth_outcome
        theirs = predict(baseline, result.row, result.current_model_prediction) == result.ground_truth_outcome
        gained += mine and not theirs
        lost += theirs and not mine
    return gained, lost


def _parameters(world: World) -> str:
    if world.rule is None:
        return "none"
    return f"required_clear={world.rule.required_clear};active={world.rule.active};prior_actor_id={world.rule.prior_actor_id}"


def _step() -> float:
    env = SalesEnvironment(chain_debug_scenario())
    micro = env.reset()
    occurrence = micro.primary_occurrence[TASK]
    env.step(AllocationAction({("deal_A", occurrence, "ae"): 1.0}))
    return env.get_state().task_progress[TASK]


def _render(
    named: tuple[WorldResult, ...],
    grid: tuple[WorldResult, ...],
    candidates: tuple[Candidate, ...],
    vectors: tuple[CandidateVector, ...],
) -> str:
    fingerprint = baseline_one_occurrence_matches_v1()
    by_name = {candidate.name: candidate for candidate in candidates}
    lines = [
        "# Ground-truth representation gap",
        "",
        "## Question",
        "",
        "Can the current Macro gate be shown incomplete when a hidden rule in the world decides an outcome the gate predicts incorrectly, and can a candidate fitted on some worlds be scored on others?",
        "",
        "## Layers",
        "",
        "Ground truth holds the decision, the eligible holders, the prior actor, and a DutyExclusion rule. The projected OrgState copies capacity, information, external information, and one AuthorityGrant per holder. It has no field for the rule. diagnose reads that state and predicts. The observation lists the gate fields, the decision id, the eligible holders, the prior actor, and the generated progress. The hidden fields required_clear and active never appear in it.",
        "",
        "## Hidden rule",
        "",
        "DutyExclusion(decision_id, prior_actor_id, required_clear, active). Clear holders are eligible holders other than the prior actor. An active rule allows progress only when the clear count reaches required_clear. An inactive or absent rule leaves the gate's answer in place.",
        "",
        "The alternatives were weaker. GovernanceBody.quorum is already stored and simply unread by the gate. SLA breach and capability requirements already have entities and events. Information expiry would read a time gap, which this repository does not read as waiting.",
        "",
        "## Worlds",
        "",
        "| scenario | split | hidden parameters | eligible holders | prior | prediction | outcome | mismatch | classification |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in named:
        lines.append(
            f"| {result.world.scenario_id} | {result.world.split} | {_parameters(result.world)} | "
            f"{', '.join(result.world.holders) or 'none'} | {result.world.prior_actor_id} | {result.current_model_prediction} | "
            f"{result.ground_truth_outcome} | {result.mismatch} | {result.classification} |"
        )
    lines.extend(
        [
            "",
            "The hidden parameters column is for the reader. It is written after evaluation and is an input to neither diagnose nor propose.",
            "",
            "## Candidates",
            "",
            f"propose sees only the public rows of {', '.join(PROPOSAL_IDS)}. Fit bias: the smallest threshold per observed decision id that agrees with every proposal row. Holdout is {', '.join(HOLDOUT_IDS)}.",
            "",
            "| candidate | fitted thresholds | admissible | fitted | proposal | holdout | coverage | contradiction resolution | regression | specificity | semantic safety | complexity | supported |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for vector in vectors:
        thresholds = ", ".join(f"{decision}={n}" for decision, n in by_name[vector.name].thresholds) or "none"
        lines.append(
            f"| {vector.name} | {thresholds} | {vector.admissible} | {vector.fitted} | {vector.proposal_matches}/{len(PROPOSAL_IDS)} | "
            f"{vector.holdout_matches}/{len(HOLDOUT_IDS)} | {vector.coverage}/{len(NAMED_IDS)} | {vector.contradiction_resolution} | "
            f"{vector.regression} | {vector.specificity} | {vector.semantic_safety} | {vector.complexity} | {vector.supported} |"
        )
    lines.extend(
        [
            "",
            "supported means admissible, fitted, and correct on every proposal and holdout world. It does not install the candidate and it is not a claim that the rule exists outside these worlds.",
            "",
            "## Extra holdout grid",
            "",
            f"{len(grid)} generated worlds: decisions {', '.join(f'{d} (required_clear {n})' for d, n in GRID_DECISIONS)}, clear-holder count 0 to 3, prior actor inside or outside the holder set, rule active or inactive. None of these rows was shown to propose.",
            "",
            "| candidate | grid correct | failures by category |",
            "| --- | --- | --- |",
        ]
    )
    for vector in vectors:
        failures = ", ".join(f"{key} {count}" for key, count in vector.grid_failures) or "none"
        lines.append(f"| {vector.name} | {vector.grid_correct}/{vector.grid_total} | {failures} |")
    gained, lost = _grid_split(by_name["DutyExclusion"], by_name["UnmodeledConstraint"], grid)
    lines.extend(
        [
            "",
            "unseen_decision: the decision id was not in any proposal row, so the candidate falls back to the gate. inactive_rule: the rule is inactive in ground truth and the observation has no field for that. prior_not_holder: the prior actor is outside the holder set, where holder count and clear count differ.",
            "",
            f"The raw grid count does not rank. DutyExclusion is correct on {gained} grid worlds where the placeholder is wrong (active rules that block), and wrong on {lost} grid worlds where the placeholder is right (inactive rules with a low clear count).",
            "",
            "## Checks that stayed in place",
            "",
            f"Macro-Micro integration rows and invariants still pass: {integration_still_passes()}.",
            f"Seed-0 FIFO fingerprint, 2 completed deals in 40 steps: {fingerprint}.",
            "TaskConstraint and the operating-model entities have no DutyExclusion field.",
            "",
            "## What the experiment demonstrates",
            "",
            "A rule stored only in the world makes the current gate predict can_progress while the generated outcome is blocked, and the gap classifier labels that a representation gap from the public record alone. A matching world on the same decision is labelled no gap. A candidate fitted on three public rows can be scored on three held-out worlds and on a generated grid, with its failures sorted by cause.",
            "",
            "## What it does not demonstrate",
            "",
            "It does not show that duty exclusion is a real organizational fact. It does not validate the ontology against enterprise data. It does not show that the search list contains every possible primitive, or that the fitted candidate is correct beyond these worlds. The named worlds do not separate DutyExclusion from DecisionQuorum; only grid rows with the prior actor outside the holder set do. No candidate observes whether a rule is active, so inactive-rule worlds with a low clear count are mispredicted by every threshold candidate.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_csv(path: Path, rows: tuple[GapRow, ...]) -> None:
    fields = (
        "scenario_id",
        "split",
        "ground_truth_hidden_primitive",
        "ground_truth_parameters",
        "observation_fields",
        "current_model_prediction",
        "ground_truth_outcome",
        "mismatch",
        "classification",
        "candidate",
        "candidate_prediction",
        "candidate_correct",
        "admissible",
        "supported",
        "regression",
        "semantic_safety",
        "complexity",
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
