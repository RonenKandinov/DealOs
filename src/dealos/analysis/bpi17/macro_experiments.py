"""Descriptive counts of org:resource on the BPI17 log.

A resource id is an observed identifier. These counts do not add a macro
primitive, a handoff, a role, or an edge.
"""

from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from dealos.analysis.bpi17.birth import collect_births
from dealos.analysis.bpi17.read import Event, load_events

LIFECYCLE_NAMES = ("schedule", "start", "suspend", "resume", "complete", "ate_abort", "withdraw")
STABILITY_CASES = 10
STABILITY_GAP = 0.10
CONCENTRATION_SHARE = 0.5
LIFECYCLE_SHARE = 0.8
LIFECYCLE_MIN_EVENTS = 100
CROSS_CASE_MIN = 30
GAP_BUCKETS = (
    ("0_1h", 0, 3600),
    ("1_4h", 3600, 4 * 3600),
    ("4_8h", 4 * 3600, 8 * 3600),
    ("8_24h", 8 * 3600, 24 * 3600),
    ("24_72h", 24 * 3600, 72 * 3600),
    ("gt_72h", 72 * 3600, None),
)


def analyze_macro(events: list[Event]) -> dict:
    grouped = _by_case(events)
    births = collect_births(events)
    birth_keys = {(row["case_id"], row["event_index"]) for row in births}
    repeated_cases = {row["case_id"] for row in births}
    resources = _resource_tables(grouped, birth_keys, repeated_cases)
    transitions = _transitions(grouped)
    lifecycle = _lifecycle(grouped, birth_keys)
    return {
        "events": len(events),
        "cases": len(grouped),
        "resources": resources,
        "transitions": transitions,
        "lifecycle": lifecycle,
        "decision": _decision(resources, transitions, lifecycle),
    }


def _resource_tables(grouped, birth_keys, repeated_cases) -> list[dict]:
    stats: dict[str, dict] = {}
    per_case: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))

    def slot(resource: str) -> dict:
        row = stats.get(resource)
        if row is None:
            row = {
                "resource": resource,
                "events": 0,
                "activities": set(),
                "workflow": set(),
                "application": set(),
                "offer": set(),
                "origins": set(),
                "cases": set(),
                "activity_counts": Counter(),
                "births_preceded": 0,
                "births_participated": 0,
                "repeated_cases": set(),
            }
            stats[resource] = row
        return row

    for case_id, rows in grouped.items():
        for index, event in enumerate(rows):
            resource = event.resource.strip()
            if not resource:
                continue
            row = slot(resource)
            row["events"] += 1
            row["activities"].add(event.activity)
            row["origins"].add(event.origin)
            row["cases"].add(case_id)
            row["activity_counts"][event.activity] += 1
            per_case[resource][case_id][event.activity] += 1
            if event.origin == "Workflow":
                row["workflow"].add(event.activity)
            elif event.origin == "Application":
                row["application"].add(event.activity)
            elif event.origin == "Offer":
                row["offer"].add(event.activity)
            if case_id in repeated_cases:
                row["repeated_cases"].add(case_id)
            if (case_id, event.event_index) in birth_keys:
                row["births_participated"] += 1
                if index:
                    previous = rows[index - 1].resource.strip()
                    if previous:
                        slot(previous)["births_preceded"] += 1
    rows_out = []
    for resource, row in stats.items():
        counts = row["activity_counts"]
        top_activity, top_count = counts.most_common(1)[0]
        global_share = top_count / row["events"]
        case_shares = []
        if len(row["cases"]) >= STABILITY_CASES:
            for case_counts in per_case[resource].values():
                case_total = sum(case_counts.values())
                case_shares.append(case_counts[top_activity] / case_total if case_total else 0.0)
        median_case_share = median(case_shares) if case_shares else None
        stable = (
            median_case_share is not None and abs(median_case_share - global_share) <= STABILITY_GAP
        )
        events_per_case = [
            sum(case_counts.values()) for case_counts in per_case[resource].values()
        ]
        rows_out.append(
            {
                "resource": resource,
                "events": row["events"],
                "activities": len(row["activities"]),
                "workflow_activities": len(row["workflow"]),
                "application_activities": len(row["application"]),
                "offer_activities": len(row["offer"]),
                "origins": len(row["origins"]),
                "top_activity": top_activity,
                "top_share": round(global_share, 4),
                "entropy_bits": round(_entropy(counts), 4),
                "cases": len(row["cases"]),
                "median_events_per_case": median(events_per_case) if events_per_case else 0,
                "median_case_top_share": None if median_case_share is None else round(median_case_share, 4),
                "profile_stable": stable,
                "repeated_cases": len(row["repeated_cases"]),
                "births_preceded": row["births_preceded"],
                "births_participated": row["births_participated"],
            }
        )
    rows_out.sort(key=lambda item: (-item["events"], item["resource"]))
    return rows_out


def _transitions(grouped) -> dict:
    cells = Counter()
    pairs: Counter[tuple[str, str]] = Counter()
    gaps = {name: Counter() for name, _low, _high in GAP_BUCKETS}
    negative_gaps = 0
    missing_id_pairs = 0
    for rows in grouped.values():
        for previous, nxt in zip(rows, rows[1:]):
            left = previous.resource.strip()
            right = nxt.resource.strip()
            same_activity = previous.activity == nxt.activity
            same_resource = bool(left) and left == right
            if not left or not right:
                missing_id_pairs += 1
                continue
            if same_resource and same_activity:
                cells["same_resource_same_activity"] += 1
            elif same_resource:
                cells["same_resource_different_activity"] += 1
            elif same_activity:
                cells["different_resource_same_activity"] += 1
            else:
                cells["different_resource_different_activity"] += 1
            if same_resource:
                continue
            pairs[(left, right)] += 1
            delta = (nxt.ts - previous.ts).total_seconds()
            if delta < 0:
                negative_gaps += 1
                continue
            label = "different_activity" if not same_activity else "same_activity"
            for name, low, high in GAP_BUCKETS:
                if delta >= low and (high is None or delta < high):
                    gaps[name][label] += 1
                    break
    ordered = pairs.most_common()
    change_events = sum(pairs.values())
    distinct_pairs = len(ordered)
    top_n = max(1, math.ceil(distinct_pairs * 0.01)) if distinct_pairs else 0
    top_count = sum(count for _pair, count in ordered[:top_n])
    top_share = (top_count / change_events) if change_events else 0.0
    reverse_hits = sum(1 for (left, right) in pairs if (right, left) in pairs)
    return {
        "cells": dict(cells),
        "pairs": [{"from_resource": left, "to_resource": right, "count": count} for (left, right), count in ordered],
        "distinct_pairs": distinct_pairs,
        "change_events": change_events,
        "top_percent_pairs": top_n,
        "top_percent_share": round(top_share, 4),
        "concentrated": top_share >= CONCENTRATION_SHARE,
        "pairs_with_reverse": reverse_hits,
        "gaps": {name: dict(counter) for name, counter in gaps.items()},
        "negative_gaps": negative_gaps,
        "missing_id_pairs": missing_id_pairs,
    }


def _lifecycle(grouped, birth_keys) -> list[dict]:
    counts: dict[str, Counter] = defaultdict(Counter)
    births = Counter()
    non_births = Counter()
    for rows in grouped.values():
        for event in rows:
            resource = event.resource.strip()
            if not resource:
                continue
            counts[resource][event.lifecycle] += 1
            if (event.case_id, event.event_index) in birth_keys:
                births[resource] += 1
            else:
                non_births[resource] += 1
    rows_out = []
    for resource, counter in counts.items():
        total = sum(counter.values())
        top_name, top_count = counter.most_common(1)[0]
        share = top_count / total if total else 0.0
        rows_out.append(
            {
                "resource": resource,
                "events": total,
                "top_lifecycle": top_name,
                "top_lifecycle_share": round(share, 4),
                "lifecycle_concentrated": total >= LIFECYCLE_MIN_EVENTS and share >= LIFECYCLE_SHARE,
                "birth_events": births[resource],
                "non_birth_events": non_births[resource],
                **{name: counter[name] for name in LIFECYCLE_NAMES},
            }
        )
    rows_out.sort(key=lambda item: (-item["events"], item["resource"]))
    return rows_out


def _decision(resources: list[dict], transitions: dict, lifecycle: list[dict]) -> dict:
    event_total = sum(row["events"] for row in resources)
    wide = [row for row in resources if row["cases"] >= CROSS_CASE_MIN]
    wide_events = sum(row["events"] for row in wide)
    activity_counts = sorted(row["activities"] for row in resources)
    median_activities = median(activity_counts) if activity_counts else 0
    high_diversity = [row for row in resources if row["activities"] >= median_activities]
    stable_wide = [row for row in wide if row["profile_stable"]]
    persistent = (
        event_total > 0
        and wide_events / event_total >= CONCENTRATION_SHARE
        and len(wide) > 0
        and len(stable_wide) / len(wide) >= CONCENTRATION_SHARE
    )
    names = []
    if persistent:
        names.append("persistent resource identifier")
    if transitions["concentrated"]:
        names.append("observed resource-id transition")
    return {
        "line": "MACRO CANDIDATE IDENTIFIED" if names else "MACRO SHOULD REMAIN MINIMAL",
        "candidates": names,
        "wide_resources": len(wide),
        "wide_event_share": round(wide_events / event_total, 4) if event_total else 0.0,
        "stable_wide_share": round(len(stable_wide) / len(wide), 4) if wide else 0.0,
        "median_activities": median_activities,
        "high_diversity_resources": len(high_diversity),
        "lifecycle_concentrated_resources": sum(row["lifecycle_concentrated"] for row in lifecycle),
        "specialized_resources": sum(row["top_share"] >= 0.8 for row in resources),
    }


def render_activity(resources: list[dict], decision: dict) -> str:
    shares = [row["top_share"] for row in resources]
    activities = [row["activities"] for row in resources]
    entropies = [row["entropy_bits"] for row in resources]
    lines = [
        "# BPI17 resource activity profiles",
        "",
        "org:resource is an observed identifier. A broad activity list is not a role, a department, or a person.",
        "",
        f"FACT: {len(resources)} resource ids. Median distinct activities {_num(median(activities) if activities else None)}. Median share in the most common activity {_num(median(shares) if shares else None)}. Median entropy {_num(median(entropies) if entropies else None)} bits.",
        f"FACT: {decision['specialized_resources']} resources have at least 80% of their events in one activity.",
        f"FACT: among resources in at least {STABILITY_CASES} cases, a profile is called stable when the median per-case share of the global top activity is within {STABILITY_GAP:.2f} of the global share. Stable share of resources that appear in at least {CROSS_CASE_MIN} cases: {decision['stable_wide_share']:.1%}.",
        "",
        "INFERENCE: identifiers that touch many activities participate across more than one observed activity name.",
        "HYPOTHESIS: such an identifier is a generalist employee. The log does not say that.",
        "",
        "| Resource | Events | Activities | Top activity | Top share | Entropy | Cases | Stable |",
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for row in resources[:15]:
        lines.append(
            f"| {row['resource']} | {row['events']} | {row['activities']} | {row['top_activity']} | {row['top_share']:.1%} | {row['entropy_bits']:.2f} | {row['cases']} | {row['profile_stable']} |"
        )
    lines.append("")
    lines.append("The table shows the 15 identifiers with the most events. The csv has every identifier.")
    return "\n".join(lines) + "\n"


def render_transitions(transitions: dict) -> str:
    cells = transitions["cells"]
    lines = [
        "# BPI17 resource-id transitions",
        "",
        "A directed pair is two different resource ids on consecutive events in the same case. The pair is an observed transition. It is not a handoff and not an organizational graph.",
        "",
        f"FACT: {transitions['change_events']} consecutive pairs change the resource id, across {transitions['distinct_pairs']} directed pairs. The most frequent 1% of those pairs ({transitions['top_percent_pairs']} pairs) cover {transitions['top_percent_share']:.1%} of the changes. Concentrated, under the half-share rule: {transitions['concentrated']}.",
        f"FACT: {transitions['pairs_with_reverse']} directed pairs also appear in the reverse direction.",
        f"FACT: consecutive pairs with a missing resource id: {transitions['missing_id_pairs']}. Negative gaps among id changes: {transitions['negative_gaps']}.",
        "",
        f"- same activity, different id: {cells.get('different_resource_same_activity', 0)}",
        f"- different activity, different id: {cells.get('different_resource_different_activity', 0)}",
        f"- same id, different activity: {cells.get('same_resource_different_activity', 0)}",
        f"- same id, same activity: {cells.get('same_resource_same_activity', 0)}",
        "",
        "Gap buckets count only pairs whose resource id changes. A bucket is not a wait.",
        "",
        "| Bucket | Same activity | Different activity |",
        "| --- | ---: | ---: |",
    ]
    for name, _low, _high in GAP_BUCKETS:
        bucket = transitions["gaps"].get(name, {})
        lines.append(
            f"| {name} | {bucket.get('same_activity', 0)} | {bucket.get('different_activity', 0)} |"
        )
    lines.append("")
    lines.append("INFERENCE: if the top 1% cover is low, id changes are spread across many pairs.")
    lines.append("HYPOTHESIS: a frequent pair is a standing organizational link. That is not established.")
    return "\n".join(lines) + "\n"


def render_lifecycle(rows: list[dict], decision: dict) -> str:
    lines = [
        "# BPI17 resource identifiers and lifecycle names",
        "",
        "A resource id on a complete event is only present on that event. It is not authority to complete. Application and offer events in this log are recorded as complete, so a high complete share can come from those origins.",
        "",
        f"FACT: {decision['lifecycle_concentrated_resources']} resources have at least {LIFECYCLE_MIN_EVENTS} events and at least {LIFECYCLE_SHARE:.0%} of them in one lifecycle name.",
        "",
        "| Resource | Events | Top lifecycle | Share | Birth events | Concentrated |",
        "| --- | ---: | --- | ---: | ---: | --- |",
    ]
    for row in rows[:15]:
        lines.append(
            f"| {row['resource']} | {row['events']} | {row['top_lifecycle']} | {row['top_lifecycle_share']:.1%} | {row['birth_events']} | {row['lifecycle_concentrated']} |"
        )
    lines.append("")
    lines.append("INFERENCE: a concentrated lifecycle share means that name dominates the identifier's events.")
    lines.append("HYPOTHESIS: the identifier is responsible for that lifecycle stage. The log does not say that.")
    return "\n".join(lines) + "\n"


def render_summary(result: dict) -> str:
    decision = result["decision"]
    resources = result["resources"]
    transitions = result["transitions"]
    shares = [row["top_share"] for row in resources]
    activities = [row["activities"] for row in resources]
    names = ", ".join(decision["candidates"]) if decision["candidates"] else "none"
    lines = [
        "# BPI17 macro experiment summary",
        "",
        f"The table has {result['cases']} cases and {result['events']} events. org:resource is the identifier on the event. No semantic field for person, role, department, owner, or authority is present, so none was substituted.",
        "",
        "## 1. What org:resource lets us observe",
        "",
        "FACT: an identifier, the activity name, the lifecycle name, the case, and the timestamp.",
        "The field does not say who the identifier is.",
        "",
        "## 2. Activity profiles",
        "",
        f"FACT: median distinct activities {_num(median(activities) if activities else None)}. Median share in the top activity {_num(median(shares) if shares else None)}. Resources with top share at least 80%: {decision['specialized_resources']}.",
        f"FACT: resources in at least {CROSS_CASE_MIN} cases account for {decision['wide_event_share']:.1%} of events. Among those resources, {decision['stable_wide_share']:.1%} have a stable top-activity share under the 0.10 rule.",
        "INFERENCE: the typical identifier is spread across many activity names.",
        "HYPOTHESIS: the identifier is a generalist employee.",
        "",
        "## 3. Transitions",
        "",
        f"FACT: {transitions['distinct_pairs']} directed pairs. The top 1% cover {transitions['top_percent_share']:.1%} of id changes. Concentrated: {transitions['concentrated']}. Reverse direction also observed for {transitions['pairs_with_reverse']} directed pairs.",
        "INFERENCE: a low top-1% share means the changes are diffuse.",
        "HYPOTHESIS: a directed pair is an organizational handoff.",
        "",
        "## 4. Lifecycle",
        "",
        f"FACT: {decision['lifecycle_concentrated_resources']} resources meet the lifecycle concentration rule. Complete events are common because application and offer rows are recorded as complete.",
        "HYPOTHESIS: presence on a complete row is authority to complete.",
        "",
        "## 5. Cross-case persistence",
        "",
        f"FACT: {decision['wide_resources']} identifiers appear in at least {CROSS_CASE_MIN} cases. Median activities per identifier: {_num(decision['median_activities'])}. Identifiers at or above that median: {decision['high_diversity_resources']}.",
        "INFERENCE: many identifiers recur across cases and activities, so they behave like persistent ids in this extract.",
        "HYPOTHESIS: the identifier is a person who owns the work.",
        "",
        "## 6. A macro-level entity",
        "",
        "Only if the persistence bar is met: resources in at least 30 cases carry at least half of events, and at least half of those resources keep a stable top-activity share. Otherwise the ids are persistent strings with unstable activity mixes, which is not enough to add an entity.",
        "",
        "## 7. A macro-level relationship",
        "",
        "Only if the top 1% of directed id pairs cover at least half of id changes. Otherwise the transitions do not form a small observed network.",
        "",
        "## 8. Facts",
        "",
        "The counts in the three reports: activity breadth, top shares, entropy, directed-pair concentration, lifecycle shares, and gap buckets.",
        "",
        "## 9. Inferences",
        "",
        "A broad activity list means the id is seen on many activity names. A diffuse pair list means changes are spread out. A stable top share means the same activity name remains common inside each case.",
        "",
        "## 10. Hypotheses",
        "",
        "Person, role, department, authority, ownership, handoff, and waiting. None of these fields exist in the log.",
        "",
        "## 11. A new macro primitive",
        "",
        f"Candidates that met a predeclared bar: {names}.",
        "A candidate is a name for a later representation discussion. It is not implemented in this pass.",
        "",
        "## 12. If a candidate is named",
        "",
        "persistent resource identifier: the id recurs across cases and its top activity share stays within 0.10 of the global share. It would let a later model point at the same id across events. It would not prove a person or a role.",
        "observed resource-id transition: a small set of directed pairs would cover at least half of id changes. It would let a later model store those observed pairs. It would not prove a handoff.",
        "",
        "## 13. If no candidate is named",
        "",
        "The ids are real and the transitions are real, and both are already describable as fields on events. Unstable mixes and a long pair list do not force a new object.",
        "",
        "## Decision",
        "",
        decision["line"],
        "",
    ]
    if decision["candidates"]:
        lines.append("Named candidates, not implemented: " + ", ".join(decision["candidates"]) + ".")
        lines.append("")
    return "\n".join(lines)


def write_macro(events: list[Event], root: Path) -> dict:
    result = analyze_macro(events)
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "bpi17_macro_resource_activity.csv", result["resources"])
    transition_rows = [
        {"slice": "pair", **row} for row in result["transitions"]["pairs"]
    ]
    for name, _low, _high in GAP_BUCKETS:
        bucket = result["transitions"]["gaps"].get(name, {})
        transition_rows.append(
            {
                "slice": "gap",
                "bucket": name,
                "same_activity": bucket.get("same_activity", 0),
                "different_activity": bucket.get("different_activity", 0),
            }
        )
    _write_csv(analysis / "bpi17_macro_resource_transitions.csv", transition_rows)
    _write_csv(analysis / "bpi17_macro_resource_lifecycle.csv", result["lifecycle"])
    (docs / "bpi17_macro_experiment.md").write_text(_one_report(result), encoding="utf-8")
    return result


def _one_report(result: dict) -> str:
    parts = [
        "# BPI17 macro experiment",
        "",
        "This file is the whole experiment: the decision, the activity profiles, the resource-id transitions, and the lifecycle counts. The csv files hold the full tables.",
        "",
        _demote(render_summary(result)),
        _demote(render_activity(result["resources"], result["decision"])),
        _demote(render_transitions(result["transitions"])),
        _demote(render_lifecycle(result["lifecycle"], result["decision"])),
    ]
    return "\n".join(parts)


def _demote(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("#"):
            lines.append("#" + line)
        else:
            lines.append(line)
    return "\n".join(lines).strip() + "\n"


def _by_case(events: list[Event]) -> dict[str, list[Event]]:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.case_id].append(event)
    for rows in grouped.values():
        rows.sort(key=lambda item: item.event_index)
    return grouped


def _entropy(counts: Counter) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    value = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        share = count / total
        value -= share * math.log2(share)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
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


def _num(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    result = write_macro(load_events(root / "data" / "bpi17" / "events_normalized.csv"), root)
    print(result["decision"]["line"], result["decision"]["candidates"])


if __name__ == "__main__":
    main()
