"""Open only the fields a hidden fact's spec already names."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from dealos.macro_world.relations.models import RelationMask, RelationSpec, relation_spec
from dealos.macro_world.relations.observe import leak_count, observe
from dealos.macro_world.relations.queries import gt_has, interpretable, recoverable
from dealos.macro_world.relations.scenarios import RelationScenario, all_relation_scenarios

SCREENED = "FIVE HIDDEN FACTS RECOVERABLE WHEN THEIR OWN FIELDS ARE EXPOSED"
REVISION = "RECOVERABILITY SCREEN REQUIRES REVISION"
UNRELATED = (
    "expose_relation_type",
    "expose_authority",
    "expose_holder_kind",
    "expose_capacity_pool",
    "expose_capacity_holder",
    "expose_information",
    "expose_organization",
    "expose_department",
    "expose_role",
)


@dataclass(frozen=True)
class ScreenRow:
    scenario_id: str
    relation_name: str
    flags_opened: tuple[str, ...]
    baseline_recoverable: bool
    opened_recoverable: bool
    opened_ambiguous: bool
    unrelated_recoverable: bool
    leaks: int

    @property
    def ok(self) -> bool:
        return (
            not self.baseline_recoverable
            and self.opened_recoverable
            and not self.opened_ambiguous
            and not self.unrelated_recoverable
            and self.leaks == 0
            and bool(self.flags_opened)
        )


def screen(seed: int = 0) -> tuple[ScreenRow, ...]:
    return tuple(_row(scenario, seed) for scenario in _hidden_facts())


def write_screen(root: Path, seed: int = 0) -> str:
    rows = screen(seed)
    return SCREENED if rows and all(row.ok for row in rows) else REVISION


def _hidden_facts() -> tuple[RelationScenario, ...]:
    chosen = []
    for scenario in all_relation_scenarios():
        if scenario.negative or not gt_has(scenario.world, scenario.relation_name):
            continue
        observations = observe(scenario.world, scenario.mask, 0)
        if interpretable(observations, scenario.mask, scenario.relation_name) and not recoverable(
            observations, scenario.mask, scenario.relation_name
        ):
            chosen.append(scenario)
    return tuple(chosen)


def _row(scenario: RelationScenario, seed: int) -> ScreenRow:
    spec = relation_spec(scenario.relation_name)
    baseline = observe(scenario.world, scenario.mask, seed)
    opened_mask, flags = _open_evidence(scenario.mask, spec)
    opened = observe(scenario.world, opened_mask, seed)
    unrelated_mask = _open_unrelated(scenario.mask, spec)
    unrelated = observe(scenario.world, unrelated_mask, seed)
    return ScreenRow(
        scenario.scenario_id,
        scenario.relation_name,
        flags,
        recoverable(baseline, scenario.mask, scenario.relation_name),
        recoverable(opened, opened_mask, scenario.relation_name),
        not interpretable(opened, opened_mask, scenario.relation_name),
        recoverable(unrelated, unrelated_mask, scenario.relation_name),
        leak_count(scenario.world, opened, opened_mask),
    )


def _open_evidence(mask: RelationMask, spec: RelationSpec) -> tuple[RelationMask, tuple[str, ...]]:
    flags = tuple(flag for flag, _key in spec.evidence_fields if not getattr(mask, flag))
    return replace(mask, **{flag: True for flag in flags}), flags


def _open_unrelated(mask: RelationMask, spec: RelationSpec) -> RelationMask:
    named = {flag for flag, _key in spec.evidence_fields}
    for flag in UNRELATED:
        if flag not in named and not getattr(mask, flag):
            return replace(mask, **{flag: True})
    return mask


def main() -> int:
    print(write_screen(Path(".")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
