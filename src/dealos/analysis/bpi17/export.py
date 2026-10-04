"""Write the BPI17 analysis tables and the validation report."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from dealos.analysis.bpi17.report import render_report


def write_outputs(result: dict, root: Path) -> None:
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_dicts(analysis / "bpi17_case_features.csv", result["cases"])
    _write_dicts(analysis / "bpi17_activity_features.csv", [_flat_activity(row) for row in result["activities"]])
    _write_dicts(analysis / "bpi17_resource_activity_matrix.csv", result["matrix"])
    _write_dicts(analysis / "bpi17_mismatch_catalog.csv", result["mismatches"])
    catalog = {key: value for key, value in result.items() if key not in {"cases", "matrix"}}
    (analysis / "bpi17_pattern_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    (docs / "bpi17_validation_report.md").write_text(render_report(result), encoding="utf-8")


def _flat_activity(row: dict) -> dict:
    flat = {key: value for key, value in row.items() if key != "lifecycle"}
    for name, count in sorted(row["lifecycle"].items()):
        flat[f"lifecycle_{name}"] = count
    return flat


def _write_dicts(path: Path, rows: list[dict]) -> None:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
