"""Where a deal is blocked, and whether the macro layer can say why.

This module does not change the simulator or the macro relation rules.
It runs one frozen capacity step and reads the existing macro evaluations.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from dealos.diagnostics.manual_scenario import chain_debug_scenario
from dealos.domain.models import AllocationAction
from dealos.macro_world.relations.models import RELATION_ENDS
from dealos.macro_world.relations.scenarios import scenario_mr_d0, scenario_mr_d1, scenario_mr_e
from dealos.macro_world.relations.validate import assess
from dealos.problem_evolution.engine import baseline_one_occurrence_matches_v1
from dealos.sim.env import SalesEnvironment

PARTIAL = "partially_representable"
GAP = "genuine_gap"
AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class BlockageResult:
    scenario_id: str
    where_shown: str
    why_shown: str
    category: str
    ambiguity: bool
    mutation_accepted: bool
    epistemic_status: str


def capacity_bottleneck() -> BlockageResult:
    """A ready task does not move when the only shared resource is given elsewhere."""

    env = SalesEnvironment(chain_debug_scenario())
    state = env.reset()
    occupied = state.primary_occurrence[("deal_B", "deal_B:B1")]
    starved = ("deal_A", "deal_A:A1")
    _state, info = env.step(AllocationAction({("deal_B", occupied, "ae"): 1.0}))
    after = env.get_state()
    starved_progress = after.task_progress[starved]
    where = (
        "deal_A:A1 stays at 0 while it is ready"
        if starved_progress == 0.0 and starved not in after.blocked_tasks
        else "capacity did not starve a ready task"
    )
    why = (
        "ae utilization is 1, so no capacity remains"
        if info.utilization.get("ae") == 1.0 and info.deltas[starved] == 0.0
        else "capacity was not exhausted"
    )
    return BlockageResult(
        "capacity",
        where,
        why + ". The macro capacity pool is not attached to this task.",
        PARTIAL,
        False,
        False,
        "FACT",
    )


def information_bottleneck() -> BlockageResult:
    linked = _joins("Information", "Task")
    return BlockageResult(
        "information",
        "Micro readiness is predecessor progress. It does not name a missing information object.",
        "Macro can store that a system produces an information object. That link does not name a deal task.",
        GAP if not linked else PARTIAL,
        False,
        False,
        "HYPOTHESIS",
    )


def authority_bottleneck() -> BlockageResult:
    evaluation, failures = assess(scenario_mr_e())
    linked = _joins("Authority", "Task")
    return BlockageResult(
        "authority",
        "An approval task can still receive allocation. Participation is enough for progress.",
        "Macro does not treat the ApproveDeal activity as an authority rule.",
        AMBIGUOUS if failures == () and evaluation.mutation_accepted is False and not linked else GAP,
        evaluation.ambiguity,
        evaluation.mutation_accepted,
        evaluation.epistemic_status,
    )


def cross_organization() -> BlockageResult:
    linked = any("Deal" in side for pair in RELATION_ENDS.values() for side in pair)
    return BlockageResult(
        "cross_organization",
        "A deal graph has no organization endpoint.",
        "A department belongs to an organization inside the macro graph only.",
        GAP if not linked else PARTIAL,
        False,
        False,
        "HYPOTHESIS",
    )


def negative_controls() -> tuple[BlockageResult, ...]:
    pair, pair_failures = assess(scenario_mr_d1())
    absent, absent_failures = assess(scenario_mr_d0())
    authority, authority_failures = assess(scenario_mr_e())
    return (
        _negative("negative_resource_pair", "Both resource ids are visible.", "collaborates_with, substitutes_for, and depends_on stay undistinguished.", pair, pair_failures),
        _negative("negative_no_relation", "Two resources appear together.", "No ground-truth relation is invented from that co-presence.", absent, absent_failures),
        _negative("negative_approval_authority", "ApproveDeal is visible for two resources.", "The activity does not establish who may authorize it.", authority, authority_failures),
    )


def all_results() -> tuple[BlockageResult, ...]:
    return (
        capacity_bottleneck(),
        information_bottleneck(),
        authority_bottleneck(),
        cross_organization(),
        *negative_controls(),
    )


def fingerprint() -> bool:
    return baseline_one_occurrence_matches_v1()


def write_report(root: Path) -> str:
    results = all_results()
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "blockage_diagnosis.csv", results)
    text = _report(results, fingerprint())
    (docs / "blockage_diagnosis.md").write_text(text, encoding="utf-8")
    return text


def _negative(scenario_id: str, where: str, why: str, evaluation, failures: tuple[str, ...]) -> BlockageResult:
    refused = failures == () and evaluation.mutation_accepted is False and evaluation.ambiguity is True
    return BlockageResult(
        scenario_id,
        where,
        why,
        AMBIGUOUS if refused else GAP,
        evaluation.ambiguity,
        evaluation.mutation_accepted,
        evaluation.epistemic_status,
    )


def _joins(left: str, right: str) -> bool:
    for source, target in RELATION_ENDS.values():
        if left in source and right in target or left in target and right in source:
            return True
    return False


def _report(results: tuple[BlockageResult, ...], micro_ok: bool) -> str:
    lines = [
        "# Blockage diagnosis",
        "",
        "Micro is asked where a deal is blocked. Macro is asked why. The two layers are not joined.",
        "",
        f"Micro V1 fingerprint, seed 0 FIFO, 2 completed deals in 40 steps: {micro_ok}.",
        "",
        "| Scenario | Category | Ambiguity | Mutation accepted | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            f"| {result.scenario_id} | {result.category} | {result.ambiguity} | {result.mutation_accepted} | {result.epistemic_status} |"
        )
    lines.extend(["", "## Readings", ""])
    for result in results:
        lines.append(f"{result.scenario_id}: {result.where_shown} {result.why_shown}")
    lines.extend(
        [
            "",
            "No new primitive is added. Capacity is partial because the frozen simulator shows a ready task starved by a shared resource, while the macro capacity pool is not attached to that task. Information, authority as a gate, and a deal that crosses organizations are gaps.",
            "",
            "The current representation does not yet show, in one model, where an enterprise deal is blocked and why.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_csv(path: Path, results: tuple[BlockageResult, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("scenario", "category", "ambiguity", "mutation_accepted", "epistemic_status", "where_shown", "why_shown"),
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "scenario": result.scenario_id,
                    "category": result.category,
                    "ambiguity": result.ambiguity,
                    "mutation_accepted": result.mutation_accepted,
                    "epistemic_status": result.epistemic_status,
                    "where_shown": result.where_shown,
                    "why_shown": result.why_shown,
                }
            )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    print(write_report(root))


if __name__ == "__main__":
    main()
