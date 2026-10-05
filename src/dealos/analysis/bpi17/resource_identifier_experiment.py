"""Representation check: persistent resource identifier against BPI17.

R0 is the frozen micro field list. R1 adds one identifier object and one
association to an occurrence. This module does not import the simulator,
does not edit TaskOccurrence, and does not store a resource-id transition.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, fields
from pathlib import Path

from dealos.analysis.bpi17.micro_experiments import _case_occurrences
from dealos.analysis.bpi17.read import Event, load_events

# Frozen micro fields. tests/test_resource_identifier_experiment.py checks
# these tuples against the dataclasses. They are copied here so this package
# does not import the core.
R0_OCCURRENCE_FIELDS = (
    "occurrence_id",
    "deal_id",
    "task_id",
    "lifecycle",
    "progress",
    "offer_id",
    "readiness_source",
)
R0_RESOURCE_FIELDS = ("resource_id", "resource_type", "capacity")
R1_IDENTIFIER_FIELDS = ("resource_id",)
R1_ASSOCIATION_FIELDS = ("resource_id", "occurrence_id")
FORBIDDEN_FIELDS = frozenset(
    {
        "person",
        "employee",
        "role",
        "department",
        "owner",
        "ownership",
        "authority",
        "handoff",
        "responsibility",
        "from_resource",
        "to_resource",
        "transition",
        "capacity",
        "resource_type",
    }
)
TERMINAL = frozenset({"complete", "withdraw", "ate_abort"})
WORKFLOW = "Workflow"
DECISION_JUSTIFIED = "MACRO PRIMITIVE JUSTIFIED"
DECISION_NOT_JUSTIFIED = "MACRO PRIMITIVE NOT JUSTIFIED"


@dataclass(frozen=True)
class PersistentResourceIdentifier:
    """One observed org:resource string. The same object is the id in every case."""

    resource_id: str

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise ValueError("resource id is empty")


@dataclass(frozen=True)
class ResourceOccurrenceAssociation:
    """A pair only. It does not say why the identifier and the occurrence co-occur."""

    resource_id: str
    occurrence_id: str

    def __post_init__(self) -> None:
        if not self.resource_id.strip() or not self.occurrence_id:
            raise ValueError("association identity is empty")


def analyze_identifier(events: list[Event]) -> dict:
    occurrences, orphans = _occurrences(events)
    _require_same_occurrences(events, occurrences)
    identifiers: dict[str, PersistentResourceIdentifier] = {}
    associations: dict[tuple[str, str], ResourceOccurrenceAssociation] = {}
    event_support: Counter[tuple[str, str]] = Counter()
    blank_events = 0
    resources_on_occurrence: dict[str, set[str]] = defaultdict(set)

    for occurrence in occurrences:
        for event in occurrence["events"]:
            resource_id = event.resource.strip()
            if not resource_id:
                blank_events += 1
                continue
            identifier = identifiers.get(resource_id)
            if identifier is None:
                identifier = PersistentResourceIdentifier(resource_id)
                identifiers[resource_id] = identifier
            key = (resource_id, occurrence["occurrence_id"])
            associations.setdefault(key, ResourceOccurrenceAssociation(resource_id, occurrence["occurrence_id"]))
            event_support[key] += 1
            resources_on_occurrence[occurrence["occurrence_id"]].add(resource_id)

    r0_occurrences = [_r0_occurrence(occurrence) for occurrence in occurrences]
    queries = _r1_queries(occurrences, associations, event_support)
    direct = _direct_counts(events)
    mismatches = _mismatches(queries, direct, orphans)
    multi = sum(len(ids) >= 2 for ids in resources_on_occurrence.values())
    cross_case = sum(len(row["cases"]) >= 2 for row in queries.values())
    summary = {
        "events": len(events),
        "cases": len({event.case_id for event in events}),
        "occurrences": len(occurrences),
        "orphan_events": len(orphans),
        "blank_events": blank_events,
        "identifiers": len(identifiers),
        "associations": len(associations),
        "cross_case_identifiers": cross_case,
        "single_case_identifiers": len(identifiers) - cross_case,
        "occurrences_with_several_identifiers": multi,
        "faithful": not mismatches,
        "mismatches": mismatches[:8],
        "forbidden_fields": _forbidden_fields(),
        "transition_pairs": 0,
        "queries": queries,
        "r0_query_result": _r0_query(r0_occurrences, next(iter(identifiers), "")),
        "same_object": _same_object(identifiers, associations),
    }
    summary["capabilities"] = _capabilities(summary)
    summary["decision"] = _decision(summary)
    return summary


def render_report(summary: dict) -> str:
    queries = sorted(summary["queries"].values(), key=lambda row: (-row["events"], row["resource_id"]))
    lines = [
        "# BPI17 persistent resource identifier",
        "",
        "This file is the whole experiment. R0 is the current micro representation. R1 is that representation plus PersistentResourceIdentifier and a Resource–TaskOccurrence association. The log is BPI17. The simulator and TaskOccurrence are unchanged. No resource-id transition is stored.",
        "",
        "## Decision rule",
        "",
        "The primitive is justified when three conditions hold together. R1 can represent all three capabilities and R0 can represent none. At least one identifier occurs in two or more cases. R1's case, activity, and event answers match the resource column on the event, the R1 objects have no role or capacity fields, and no transition pair is stored.",
        "",
        "## What each representation holds",
        "",
        f"R0 TaskOccurrence fields: {', '.join(R0_OCCURRENCE_FIELDS)}.",
        f"R0 Resource fields: {', '.join(R0_RESOURCE_FIELDS)}. That object is a capacity pool. The log has no capacity and no resource type for org:resource.",
        f"R1 PersistentResourceIdentifier fields: {', '.join(R1_IDENTIFIER_FIELDS)}.",
        f"R1 ResourceOccurrenceAssociation fields: {', '.join(R1_ASSOCIATION_FIELDS)}.",
        "An event index is kept only as a counter of log rows that support a pair. It is not an object in R1.",
        "",
        "## Log counts",
        "",
        f"FACT: {summary['events']} events, {summary['cases']} cases, {summary['occurrences']} occurrences.",
        f"FACT: {summary['identifiers']} distinct org:resource strings, {summary['associations']} resource–occurrence pairs.",
        f"FACT: {summary['cross_case_identifiers']} identifiers appear in two or more cases. {summary['single_case_identifiers']} appear in one case.",
        f"FACT: {summary['blank_events']} events have an empty resource id. {summary['orphan_events']} workflow events fall outside the existing occurrence rule.",
        f"FACT: {summary['occurrences_with_several_identifiers']} occurrences contain two or more distinct resource ids. Each id is its own pair. The pairs are not a transition.",
        f"FACT: R1 matches the event column on every identifier: {summary['faithful']}.",
        *_capability_section(summary["capabilities"][0]),
        *_capability_section(summary["capabilities"][1]),
        *_capability_section(summary["capabilities"][2]),
        "",
        "## Persistence query check",
        "",
        "The three R1 answers were compared with a direct read of the resource column: cases, activity names, and events. Occurrence counts use the existing occurrence rule.",
        "",
        "| Resource id | Cases | Activity names | Occurrences | Events |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in queries[:15]:
        lines.append(
            f"| {row['resource_id']} | {row['case_count']} | {row['activity_count']} | {row['occurrence_count']} | {row['events']} |"
        )
    lines.extend(
        [
            "",
            f"The table shows the 15 identifiers with the most events. All {summary['identifiers']} identifiers are in the csv.",
            "",
            "## Epistemic limit",
            "",
            "FACT: the identifier is the org:resource string, and the association is the pair of that string with an occurrence id.",
            "The objects do not carry a person, a role, a department, ownership, authority, a handoff, or a responsibility.",
            "",
            "## Decision",
            "",
            summary["decision"],
            "",
        ]
    )
    return "\n".join(lines)


def write_identifier_experiment(events: list[Event], root: Path) -> dict:
    summary = analyze_identifier(events)
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    rows = sorted(summary["queries"].values(), key=lambda row: (-row["events"], row["resource_id"]))
    _write_csv(
        analysis / "bpi17_resource_identifier_queries.csv",
        [
            {
                "resource_id": row["resource_id"],
                "cases": row["case_count"],
                "activity_names": row["activity_count"],
                "occurrences": row["occurrence_count"],
                "events": row["events"],
                "cross_case": row["case_count"] >= 2,
            }
            for row in rows
        ],
    )
    (docs / "bpi17_resource_identifier_experiment.md").write_text(render_report(summary), encoding="utf-8")
    return summary


def _occurrences(events: list[Event]) -> tuple[list[dict], list[Event]]:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.case_id].append(event)
    records: list[dict] = []
    orphans: list[Event] = []
    for case_id, rows in grouped.items():
        rows.sort(key=lambda item: item.event_index)
        current: dict[str, list[Event]] = {}
        numbers: Counter[str] = Counter()

        def close(activity: str) -> None:
            bucket = current.pop(activity, None)
            if not bucket:
                return
            number = numbers[activity]
            records.append(
                {
                    "occurrence_id": f"{case_id}:{activity}#{number}",
                    "deal_id": case_id,
                    "task_id": activity,
                    "number": number,
                    "events": bucket,
                }
            )

        for event in rows:
            activity = event.activity
            if event.origin == WORKFLOW:
                opened = event.lifecycle == "schedule" or (event.lifecycle == "start" and activity not in current)
                if opened:
                    close(activity)
                    numbers[activity] += 1
                    current[activity] = [event]
                elif activity in current:
                    current[activity].append(event)
                else:
                    orphans.append(event)
                if event.lifecycle in TERMINAL and activity in current:
                    close(activity)
            else:
                numbers[activity] += 1
                records.append(
                    {
                        "occurrence_id": f"{case_id}:{activity}#{numbers[activity]}",
                        "deal_id": case_id,
                        "task_id": activity,
                        "number": numbers[activity],
                        "events": [event],
                    }
                )
        for activity in list(current):
            close(activity)
    return records, orphans


def _require_same_occurrences(events: list[Event], occurrences: list[dict]) -> None:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.case_id].append(event)
    expected: list[tuple[str, str, int, int]] = []
    for case_id, rows in grouped.items():
        rows.sort(key=lambda item: item.event_index)
        for record in _case_occurrences(case_id, rows):
            expected.append((case_id, record["activity"], record["occurrence_number"], record["lifecycle_events"]))
    actual = [
        (row["deal_id"], row["task_id"], row["number"], len(row["events"]))
        for row in occurrences
    ]
    if actual != expected:
        raise RuntimeError("occurrence identity drifted from the existing lifecycle walker")


def _r0_occurrence(occurrence: dict) -> dict:
    return {
        "occurrence_id": occurrence["occurrence_id"],
        "deal_id": occurrence["deal_id"],
        "task_id": occurrence["task_id"],
        "lifecycle": None,
        "progress": None,
        "offer_id": None,
        "readiness_source": None,
    }


def _r0_query(occurrences: list[dict], resource_id: str) -> dict | None:
    """Cases, activity names, and counts for one id, using only R0 occurrence fields."""

    if "resource_id" not in R0_OCCURRENCE_FIELDS and "resource" not in R0_OCCURRENCE_FIELDS:
        return None
    matched = [row for row in occurrences if row.get("resource_id") == resource_id or row.get("resource") == resource_id]
    return {
        "cases": {row["deal_id"] for row in matched},
        "activities": {row["task_id"] for row in matched},
        "occurrences": len(matched),
    }


def _r1_queries(occurrences, associations, event_support) -> dict[str, dict]:
    by_id = {row["occurrence_id"]: row for row in occurrences}
    queries: dict[str, dict] = {}
    cases: dict[str, set[str]] = defaultdict(set)
    activities: dict[str, set[str]] = defaultdict(set)
    occurrence_ids: dict[str, set[str]] = defaultdict(set)
    events: Counter[str] = Counter()
    for (resource_id, occurrence_id), association in associations.items():
        if association.resource_id != resource_id or association.occurrence_id != occurrence_id:
            raise RuntimeError("association fields do not match the pair")
        occurrence = by_id[occurrence_id]
        cases[resource_id].add(occurrence["deal_id"])
        activities[resource_id].add(occurrence["task_id"])
        occurrence_ids[resource_id].add(occurrence_id)
        events[resource_id] += event_support[(resource_id, occurrence_id)]
    for resource_id in cases:
        queries[resource_id] = {
            "resource_id": resource_id,
            "cases": cases[resource_id],
            "case_count": len(cases[resource_id]),
            "activities": activities[resource_id],
            "activity_count": len(activities[resource_id]),
            "occurrence_count": len(occurrence_ids[resource_id]),
            "events": events[resource_id],
        }
    return queries


def _direct_counts(events: list[Event]) -> dict[str, dict]:
    cases: dict[str, set[str]] = defaultdict(set)
    activities: dict[str, set[str]] = defaultdict(set)
    counts: Counter[str] = Counter()
    for event in events:
        resource_id = event.resource.strip()
        if not resource_id:
            continue
        cases[resource_id].add(event.case_id)
        activities[resource_id].add(event.activity)
        counts[resource_id] += 1
    return {
        resource_id: {
            "cases": cases[resource_id],
            "activities": activities[resource_id],
            "events": counts[resource_id],
        }
        for resource_id in counts
    }


def _mismatches(queries: dict[str, dict], direct: dict[str, dict], orphans: list[Event]) -> list[str]:
    found: list[str] = []
    orphan_counts = Counter(event.resource.strip() for event in orphans if event.resource.strip())
    if set(queries) != set(direct):
        found.append("identifier set differs from the resource column")
    for resource_id, expected in direct.items():
        actual = queries.get(resource_id)
        if actual is None:
            found.append(f"{resource_id} missing from R1")
            continue
        if actual["cases"] != expected["cases"]:
            found.append(f"{resource_id} cases differ")
        if actual["activities"] != expected["activities"]:
            found.append(f"{resource_id} activities differ")
        if actual["events"] + orphan_counts[resource_id] != expected["events"]:
            found.append(f"{resource_id} events differ")
    return found


def _same_object(identifiers, associations) -> bool:
    if len({id(item) for item in identifiers.values()}) != len(identifiers):
        return False
    for resource_id, _occurrence_id in associations:
        found = identifiers.get(resource_id)
        if found is None or found.resource_id != resource_id:
            return False
    return True


def _forbidden_fields() -> list[str]:
    present = []
    for cls in (PersistentResourceIdentifier, ResourceOccurrenceAssociation):
        for field in fields(cls):
            if field.name in FORBIDDEN_FIELDS:
                present.append(f"{cls.__name__}.{field.name}")
    return present


def _capabilities(summary: dict) -> list[dict]:
    r0 = summary["r0_query_result"] is not None
    r1 = summary["same_object"] and not summary["forbidden_fields"] and summary["transition_pairs"] == 0
    cross_events = sum(row["events"] for row in summary["queries"].values() if row["case_count"] >= 2)
    several = summary["occurrences_with_several_identifiers"]
    return [
        {
            "name": "Cross-case identity",
            "question": "Can the representation state that the same org:resource identifier appears in more than one case?",
            "r0": r0,
            "r1": r1,
            "new_relation": False,
            "evidence": (
                f"FACT: {summary['cross_case_identifiers']} of {summary['identifiers']} identifiers appear in two or more cases, "
                f"covering {cross_events} events. "
                "R0 occurrences have no resource field, and R0 Resource does not record case membership. "
                "R1 keeps one PersistentResourceIdentifier per string, and the case set is read from the associations."
            ),
            "status": "FACT",
        },
        {
            "name": "Resource-occurrence association",
            "question": "Can the representation state an explicit Resource to TaskOccurrence pair with no further semantics?",
            "r0": False,
            "r1": r1 and summary["faithful"],
            "new_relation": True,
            "evidence": (
                f"FACT: {summary['associations']} pairs. "
                f"FACT: {several} occurrences have more than one resource id, stored as separate pairs. "
                "R0's only resource-bearing triple is an allocation amount, which is a capacity fraction, so it is not this pair. "
                "R1's association has resource_id and occurrence_id."
            ),
            "status": "FACT",
        },
        {
            "name": "Persistence queries",
            "question": "Can the representation answer which cases, which activity names, and how many occurrences and events belong to resource r?",
            "r0": r0,
            "r1": r1 and summary["faithful"],
            "new_relation": False,
            "evidence": (
                f"FACT: R1 matches the resource column for cases, activity names, and events: {summary['faithful']}. "
                "R0 returns no case list, no activity list, and no count. "
                "The occurrence count is the number of pairs for that id."
            ),
            "status": "FACT",
        },
    ]


def _decision(summary: dict) -> str:
    capabilities = summary["capabilities"]
    r1_only = all(row["r1"] and not row["r0"] for row in capabilities)
    observed = summary["cross_case_identifiers"] >= 1 and summary["associations"] >= 1
    clean = summary["faithful"] and not summary["forbidden_fields"] and summary["transition_pairs"] == 0
    if r1_only and observed and clean:
        return DECISION_JUSTIFIED
    return DECISION_NOT_JUSTIFIED


def _capability_section(row: dict) -> list[str]:
    both = row["r0"] and row["r1"]
    if both:
        relation = "yes" if row["new_relation"] else "no"
    else:
        relation = "not applicable"
    lines = [
        "",
        f"## {row['name']}",
        "",
        row["question"],
        "",
        f"Representable in R0: {'yes' if row['r0'] else 'no'}.",
        f"Representable in R1: {'yes' if row['r1'] else 'no'}.",
        f"New object-level relation when both can represent it: {relation}.",
    ]
    if row["new_relation"] and not both:
        lines.append("The Resource–TaskOccurrence pair is an object in R1.")
    lines.extend([row["evidence"], f"Epistemic status: {row['status']}."])
    return lines


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    summary = write_identifier_experiment(load_events(root / "data" / "bpi17" / "events_normalized.csv"), root)
    print(summary["decision"])


if __name__ == "__main__":
    main()
