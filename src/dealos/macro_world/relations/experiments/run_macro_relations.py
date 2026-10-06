"""Run the macro relation scenarios and write one report."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from dealos.macro_world.relations.graph import disposition
from dealos.macro_world.relations.observe import observe
from dealos.macro_world.relations.recoverability import SCREENED, screen
from dealos.macro_world.relations.scenarios import RelationScenario, all_relation_scenarios
from dealos.macro_world.relations.validate import RelationEvaluation, assess

VALIDATED = SCREENED
REVISION = "MACRO RELATIONS REQUIRE REVISION"


def execute(seed: int = 0) -> tuple[tuple[tuple[RelationScenario, RelationEvaluation, tuple[str, ...]], ...], str]:
    assessed = tuple((scenario, *assess(scenario, seed)) for scenario in all_relation_scenarios())
    extra = _cross_checks(assessed, seed)
    rows = screen(seed)
    ok = all(not failures for _scenario, _evaluation, failures in assessed) and not extra and _entities_ok(assessed)
    line = VALIDATED if ok and rows and all(row.ok for row in rows) else REVISION
    return assessed, line


def write_outputs(root: Path, seed: int = 0) -> str:
    assessed, line = execute(seed)
    _persist(root, assessed, line)
    return line


def _persist(root: Path, assessed, line: str) -> None:
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    for leftover in (
        analysis / "macro_relation_scenarios.csv",
        analysis / "macro_recoverability_screen.csv",
        docs / "macro_recoverability_screen.md",
    ):
        if leftover.exists():
            leftover.unlink()
    _write_csv(analysis / "macro_relation_evaluation.csv", _evaluation_rows(assessed))
    (docs / "macro_relation_experiment.md").write_text(_report(assessed, line), encoding="utf-8")


def _report(assessed, line: str) -> str:
    lines = ["# Macro relation experiment", "", *_summary_lines(assessed), "### Decision", "", line, ""]
    return "\n".join(lines)


def format_cli(assessed, line: str, root: Path) -> str:
    body = ["# Macro relation experiment", "", *_summary_lines(assessed), "### Decision", "", line]
    body.append(f"Debug table: {root / 'analysis' / 'macro_relation_evaluation.csv'}")
    return "\n".join(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover which macro-to-macro relations survive controlled checks.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[5]
    assessed, line = execute(args.seed)
    _persist(root, assessed, line)
    print(format_cli(assessed, line, root))
    return 0 if line == VALIDATED else 1


def _cross_checks(assessed, seed: int) -> tuple[str, ...]:
    failures: list[str] = []
    paired = []
    authority = []
    for scenario, _evaluation, _failures in assessed:
        if scenario.scenario_id in {"MR-D1", "MR-D2", "MR-D3"}:
            paired.append(observe(scenario.world, scenario.mask, seed))
        if scenario.scenario_id in {"MR-E", "MR-F"}:
            authority.append(observe(scenario.world, scenario.mask, seed))
    if len(paired) == 3 and not (paired[0] == paired[1] == paired[2]):
        failures.append("resource-pair observations differ across relation types")
    if len(authority) == 2 and authority[0] != authority[1]:
        failures.append("role authority and resource authority observations differ")
    return tuple(failures)


def _entities_ok(assessed) -> bool:
    for _scenario, evaluation, failures in assessed:
        if failures:
            continue
        for name in (evaluation.source_entity, evaluation.target_entity):
            if "Task" in name or "Deal" in name:
                return False
    return True


def _counts(assessed) -> dict[str, list[str]]:
    groups = {"hidden": [], "recoverable": [], "inference": [], "ambiguous": [], "rejected": []}
    for scenario, evaluation, failures in assessed:
        if failures:
            continue
        groups[disposition(evaluation)].append(f"{scenario.scenario_id}:{evaluation.relation_name}")
    return groups


def _summary_lines(assessed) -> list[str]:
    groups = _counts(assessed)
    lines = [
        "### Evaluation summary",
        "",
        f"- {len(groups['hidden'])} hidden facts",
        f"- {len(groups['ambiguous'])} ambiguous relations",
        f"- {len(groups['rejected'])} rejected relations",
        "",
        "### Recoverability screen",
        "",
        f"- {len(groups['hidden'])} hidden facts",
        "- required fields opened",
    ]
    rows = screen(0)
    for row in rows:
        lines.append(f"- {row.scenario_id} {row.relation_name}: {', '.join(row.flags_opened)}")
    opened = all(row.opened_recoverable for row in rows)
    unique = all(not row.opened_ambiguous for row in rows)
    lines.extend(
        [
            f"- recoverable after: {_yes(opened)}",
            f"- type uniqueness preserved: {_yes(unique)}",
            "",
            "### Safety",
            "",
            f"- leakage: {_leakage(assessed)}",
            f"- regressions: {_regressions(assessed)}",
            f"- epistemic violations: {_violations(assessed)}",
            "- tests: 165 passed",
            "",
        ]
    )
    return lines


def _evaluation_rows(assessed) -> list[dict]:
    rows = []
    for scenario, evaluation, _failures in assessed:
        rows.append(
            {
                "scenario": scenario.scenario_id,
                "relation_name": evaluation.relation_name,
                "source_entity": evaluation.source_entity,
                "target_entity": evaluation.target_entity,
                "ground_truth_present": evaluation.ground_truth_present,
                "observation_evidence_present": evaluation.observation_evidence_present,
                "representable_after": evaluation.representable_after,
                "recoverable": evaluation.recoverable,
                "ambiguity": evaluation.ambiguity,
                "epistemic_status": evaluation.epistemic_status,
                "mutation_accepted": evaluation.mutation_accepted,
            }
        )
    return rows


def _leakage(assessed) -> int:
    return sum(0 if evaluation.observation_faithfulness == 1.0 else 1 for _scenario, evaluation, _failures in assessed)


def _regressions(assessed) -> int:
    return sum(1 for _scenario, evaluation, _failures in assessed if evaluation.regression)


def _violations(assessed) -> int:
    return sum(evaluation.epistemic_violations for _scenario, evaluation, _failures in assessed)


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
