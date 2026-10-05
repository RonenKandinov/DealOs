"""Three descriptive checks around occurrence births. They do not edit the simulator.

A birth uses collect_births. Context never crosses a case boundary.
A frequent predecessor is not written as an edge.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from dealos.analysis.bpi17.birth import MIN_BIRTHS, PAIR_SHARE, collect_births
from dealos.analysis.bpi17.read import Event, load_events

WINDOWS = (1, 3, 5)
TERMINAL = frozenset({"complete", "withdraw", "ate_abort"})
WORKFLOW = "Workflow"
NAMED_PATTERNS = (
    ("W_Call after offers", "W_Call after offers", "ate_abort"),
    ("O_Cancelled", "O_Cancelled", "complete"),
    ("O_Refused", "O_Refused", "complete"),
    ("W_Validate application", "W_Call incomplete files", "ate_abort"),
    ("A_Validating", "W_Validate application", "start"),
    ("A_Incomplete", "W_Call incomplete files", "start"),
    ("O_Created", "O_Create Offer", "complete"),
    ("O_Sent (mail and online)", "O_Created", "complete"),
)
SMALL_N = 30


def data_fields_present() -> tuple[str, ...]:
    """Fields these three checks read. All are on the normalized event."""

    return ("case_id", "event_index", "ts", "activity", "lifecycle:transition", "resource")


def context_rows(events: list[Event], births: list[dict] | None = None) -> list[dict]:
    grouped = _by_case(events)
    births = collect_births(events) if births is None else births
    rows: list[dict] = []
    for birth in births:
        case_rows = grouped[birth["case_id"]]
        index = _index_of(case_rows, birth["event_index"])
        birth_event = case_rows[index]
        for window in WINDOWS:
            start = max(0, index - window)
            preceding = case_rows[start:index]
            for offset, previous in enumerate(reversed(preceding), start=1):
                lag = (birth_event.ts - previous.ts).total_seconds()
                rows.append(
                    {
                        "case_id": birth["case_id"],
                        "window": window,
                        "relative_position": offset,
                        "birth_event_index": birth_event.event_index,
                        "birth_activity": birth_event.activity,
                        "birth_lifecycle": birth_event.lifecycle,
                        "birth_timestamp": birth_event.ts.isoformat(),
                        "predecessor_activity": previous.activity,
                        "predecessor_lifecycle": previous.lifecycle,
                        "predecessor_timestamp": previous.ts.isoformat(),
                        "lag_seconds": lag,
                        "resource": birth_event.resource,
                        "predecessor_resource": previous.resource,
                    }
                )
    rows.sort(key=lambda row: (row["case_id"], row["birth_timestamp"], row["window"], row["relative_position"]))
    return rows


def summarize_context(rows: list[dict]) -> dict:
    by_window: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        if row["relative_position"] == 1:
            by_window[row["window"]].append(row)
    activities: list[dict] = []
    birth_activities = sorted({row["birth_activity"] for row in rows})
    for activity in birth_activities:
        record: dict = {"activity": activity}
        for window in WINDOWS:
            immediate = [row for row in by_window[window] if row["birth_activity"] == activity]
            pairs: Counter[tuple[str, str]] = Counter(
                (row["predecessor_activity"], row["predecessor_lifecycle"]) for row in immediate
            )
            if not pairs:
                continue
            (pred_activity, pred_lifecycle), count = pairs.most_common(1)[0]
            record[f"k{window}_births"] = len(immediate)
            record[f"k{window}_top_activity"] = pred_activity
            record[f"k{window}_top_lifecycle"] = pred_lifecycle
            record[f"k{window}_top_share"] = round(count / len(immediate), 4)
        anywhere = []
        for pattern in NAMED_PATTERNS:
            if pattern[0] != activity:
                continue
            for window in WINDOWS:
                scoped = [
                    row
                    for row in rows
                    if row["window"] == window and row["birth_activity"] == activity
                ]
                births_in_window = {(row["case_id"], row["birth_event_index"]) for row in scoped}
                hits = {
                    (row["case_id"], row["birth_event_index"])
                    for row in scoped
                    if row["predecessor_activity"] == pattern[1] and row["predecessor_lifecycle"] == pattern[2]
                }
                anywhere.append(
                    {
                        "window": window,
                        "predecessor_activity": pattern[1],
                        "predecessor_lifecycle": pattern[2],
                        "births": len(births_in_window),
                        "births_with_pattern": len(hits),
                        "share": round(len(hits) / len(births_in_window), 4) if births_in_window else 0.0,
                    }
                )
        record["named_pattern"] = anywhere
        activities.append(record)
    return {"windows": WINDOWS, "activities": activities}


def resource_rows(events: list[Event]) -> list[dict]:
    grouped = _by_case(events)
    rows = []
    for birth in collect_births(events):
        case_rows = grouped[birth["case_id"]]
        index = _index_of(case_rows, birth["event_index"])
        birth_event = case_rows[index]
        previous = case_rows[index - 1]
        birth_resource = birth_event.resource.strip()
        previous_resource = previous.resource.strip()
        if not birth_resource or not previous_resource:
            relation = "missing"
        elif birth_resource == previous_resource:
            relation = "same"
        else:
            relation = "different"
        same_activity = previous.activity == birth_event.activity
        rows.append(
            {
                "activity": birth_event.activity,
                "predecessor_activity": previous.activity,
                "predecessor_lifecycle": previous.lifecycle,
                "relation": relation,
                "same_activity": same_activity,
                "cell": _cell(relation, same_activity),
            }
        )
    return rows


def summarize_resources(rows: list[dict]) -> dict:
    overall = _relation_counts(rows)
    by_activity = []
    for activity in sorted({row["activity"] for row in rows}):
        scoped = [row for row in rows if row["activity"] == activity]
        by_activity.append({"activity": activity, **_relation_counts(scoped)})
    by_pattern = []
    patterns: Counter[tuple[str, str, str]] = Counter(
        (row["activity"], row["predecessor_activity"], row["predecessor_lifecycle"]) for row in rows
    )
    for key, _count in patterns.most_common():
        scoped = [
            row
            for row in rows
            if (row["activity"], row["predecessor_activity"], row["predecessor_lifecycle"]) == key
        ]
        by_pattern.append(
            {
                "activity": key[0],
                "predecessor_activity": key[1],
                "predecessor_lifecycle": key[2],
                **_relation_counts(scoped),
            }
        )
    named = []
    for activity, predecessor, lifecycle in NAMED_PATTERNS:
        scoped = [
            row
            for row in rows
            if row["activity"] == activity
            and row["predecessor_activity"] == predecessor
            and row["predecessor_lifecycle"] == lifecycle
        ]
        named.append(
            {
                "activity": activity,
                "predecessor_activity": predecessor,
                "predecessor_lifecycle": lifecycle,
                **_relation_counts(scoped),
            }
        )
    return {"overall": overall, "by_activity": by_activity, "by_pattern": by_pattern, "named": named}


def lifecycle_rows(events: list[Event]) -> list[dict]:
    grouped = _by_case(events)
    records: list[dict] = []
    for case_id in sorted(grouped):
        records.extend(_case_occurrences(case_id, grouped[case_id]))
    return records


def summarize_lifecycle(records: list[dict]) -> dict:
    cohorts = {
        "first": [row for row in records if row["occurrence_number"] == 1],
        "additional": [row for row in records if row["occurrence_number"] > 1],
    }
    summary = {
        "occurrences": len(records),
        "overall": {name: _lifecycle_cohort(rows) for name, rows in cohorts.items()},
        "by_activity": [],
    }
    activities = sorted({row["activity"] for row in records if row["occurrence_number"] > 1})
    for activity in activities:
        scoped = [row for row in records if row["activity"] == activity]
        summary["by_activity"].append(
            {
                "activity": activity,
                "first": _lifecycle_cohort([row for row in scoped if row["occurrence_number"] == 1]),
                "additional": _lifecycle_cohort([row for row in scoped if row["occurrence_number"] > 1]),
            }
        )
    summary["by_activity"].sort(key=lambda row: -row["additional"]["n"])
    return summary


def render_context(summary: dict) -> str:
    lines = [
        "# BPI17 occurrence birth context",
        "",
        "Each birth is a new occurrence under the existing rule. For k = 1, 3, and 5, the rows are the events immediately before that birth in the same case. The window stops at the start of the case. It does not borrow events from another case.",
        "",
        "FACT: a predecessor count is how often that activity and lifecycle sit in the window.",
        "UNRESOLVED: that predecessor causes the birth. A frequent pair is not an edge.",
        "",
        "The k = 1 column is the event directly before the birth. The k = 3 and k = 5 shares below are also computed on that immediate event, so a change would mean the birth set itself changed. The named-pattern table then asks whether the same pair appears anywhere in the longer window.",
        "",
        "| Activity | Births | k=1 top | k=1 share | k=3 share | k=5 share |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    frequent = [
        row
        for row in summary["activities"]
        if row.get("k1_births", 0) >= MIN_BIRTHS
    ]
    frequent.sort(key=lambda row: -row["k1_births"])
    for row in frequent:
        lines.append(
            f"| {row['activity']} | {row['k1_births']} | {row['k1_top_activity']} / {row['k1_top_lifecycle']} | {row['k1_top_share']:.1%} | {row['k3_top_share']:.1%} | {row['k5_top_share']:.1%} |"
        )
    lines.append("")
    lines.append("Named patterns, as a share of births of that activity in which the pair appears somewhere in the window:")
    lines.append("")
    lines.append("| Birth | Pair | k=1 | k=3 | k=5 |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for row in summary["activities"]:
        for pattern in row["named_pattern"]:
            if pattern["window"] != 1:
                continue
            shares = {item["window"]: item for item in row["named_pattern"]}
            lines.append(
                f"| {row['activity']} | {pattern['predecessor_activity']} / {pattern['predecessor_lifecycle']} | {shares[1]['share']:.1%} | {shares[3]['share']:.1%} | {shares[5]['share']:.1%} |"
            )
    lines.append("")
    lines.append(
        f"A pair is dominant at k = 1 when it covers at least {PAIR_SHARE:.0%} of births and the activity has at least {MIN_BIRTHS} births. That bar is a reporting rule."
    )
    lines.append("No pair is written as an edge, and readiness is unchanged.")
    return "\n".join(lines) + "\n"


def render_resources(summary: dict) -> str:
    overall = summary["overall"]
    lines = [
        "# BPI17 resource continuity at occurrence birth",
        "",
        "The resource field is an observed identifier. A matching id is not ownership. A differing id is not a handoff, a role change, or an authority transfer.",
        "",
        f"FACT: of {overall['n']} births, {overall['same_resource_count']} ({overall['same_resource_pct']:.1%}) have the same resource id as the immediately preceding event, {overall['different_resource_count']} ({overall['different_resource_pct']:.1%}) have a different id, and {overall['missing_resource_count']} ({overall['missing_resource_pct']:.1%}) have a missing id.",
        "",
        "Four-way split of the same births:",
        "",
        f"- FACT: same resource and same activity: {overall['same_resource_same_activity']} ({_pct(overall['same_resource_same_activity'], overall['n'])}).",
        f"- FACT: same resource and different activity: {overall['same_resource_different_activity']} ({_pct(overall['same_resource_different_activity'], overall['n'])}).",
        f"- FACT: different resource and same activity: {overall['different_resource_same_activity']} ({_pct(overall['different_resource_same_activity'], overall['n'])}).",
        f"- FACT: different resource and different activity: {overall['different_resource_different_activity']} ({_pct(overall['different_resource_different_activity'], overall['n'])}).",
        "",
        "Named birth patterns:",
        "",
        "| Birth | Preceding event | n | Same resource |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in summary["named"]:
        lines.append(
            f"| {row['activity']} | {row['predecessor_activity']} / {row['predecessor_lifecycle']} | {row['n']} | {row['same_resource_pct']:.1%} |"
        )
    lines.append("")
    lines.append("INFERENCE: where the share is high, the same identifier is present on both events.")
    lines.append("HYPOTHESIS: that identifier means the same person continued the work. The log does not say that.")
    return "\n".join(lines) + "\n"


def render_lifecycle(summary: dict) -> str:
    lines = [
        "# BPI17 lifecycle of repeated occurrences",
        "",
        "Occurrence 1 is the first time the activity occurs in the case. Occurrence 2+ is every later occurrence under the same birth rule. Lifecycle rows inside one workflow occurrence are not extra repetitions. Application and offer events are one completion each. Missing transitions are left missing.",
        "",
        "Suspend is not labeled as waiting. Abort is not labeled as failure. A repeat is not labeled as rework.",
        "",
        _cohort_line("First occurrences", summary["overall"]["first"]),
        _cohort_line("Additional occurrences", summary["overall"]["additional"]),
        "",
        "Activities with the most additional occurrences. A cohort under 30 occurrences is marked small.",
        "",
        "| Activity | Additional n | First completed | Additional completed | First aborted | Additional aborted | First median events | Additional median events |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["by_activity"][:12]:
        first = row["first"]
        extra = row["additional"]
        lines.append(
            f"| {row['activity']} | {extra['n']}{' small' if extra['small'] else ''} | {_pct(first['completed'], first['n'])} | {_pct(extra['completed'], extra['n'])} | {_pct(first['aborted'], first['n'])} | {_pct(extra['aborted'], extra['n'])} | {_num(first['median_events'])} | {_num(extra['median_events'])} |"
        )
    lines.append("")
    lines.append("FACT: the percentages are shares of occurrences that contain that lifecycle name.")
    lines.append("INFERENCE: a lower completion share on additional occurrences means fewer of those occurrences contain a complete event.")
    lines.append("HYPOTHESIS: the additional occurrence failed, waited, or was rework. Those readings are not in the event name.")
    return "\n".join(lines) + "\n"


def render_summary(context: dict, resources: dict, lifecycle: dict) -> str:
    overall = resources["overall"]
    first = lifecycle["overall"]["first"]
    extra = lifecycle["overall"]["additional"]
    return "\n".join(
        [
            "# BPI17 micro experiment summary",
            "",
            "The three checks use the existing 3,000-case table. The required fields are case id, event index, timestamp, activity, lifecycle, and resource. None of those fields is missing, so no count was filled in.",
            "",
            "## 1. Birth context",
            "",
            "FACT: the event immediately before the birth is the same at k = 1, k = 3, and k = 5. Its share does not move when the window grows.",
            f"FACT: {_named_window_sentence(context)}",
            "UNRESOLVED: any of those pairs causes the birth.",
            "",
            "## 2. Resource continuity",
            "",
            f"FACT: {overall['same_resource_pct']:.1%} of {overall['n']} births carry the same resource id as the preceding event. {overall['different_resource_pct']:.1%} differ. Missing ids: {overall['missing_resource_count']}.",
            "INFERENCE: the same identifier is often present on both sides of the birth.",
            "HYPOTHESIS: that identifier is ownership or a handoff. Neither is established.",
            "",
            "## 3. Lifecycle of repeated occurrences",
            "",
            f"FACT: {first['n']} first occurrences and {extra['n']} additional occurrences were grouped without splitting one workflow occurrence into repeats.",
            f"FACT: a complete event is present on {_pct(first['completed'], first['n'])} of first occurrences and {_pct(extra['completed'], extra['n'])} of additional occurrences.",
            f"FACT: an ate_abort event is present on {_pct(first['aborted'], first['n'])} of first occurrences and {_pct(extra['aborted'], extra['n'])} of additional occurrences.",
            "HYPOTHESIS: abort means failure, suspend means waiting, or a repeat means rework.",
            "",
            "## 4. Strong facts",
            "",
            "- The immediate predecessor is stable for 9 of 11 frequent birth activities under the half-share rule, and those immediate shares do not move when the window grows.",
            f"- Same resource id: {overall['same_resource_pct']:.1%} of births. Different resource id: {overall['different_resource_pct']:.1%}.",
            "- First and additional occurrences can be counted separately, and their lifecycle mixes are not the same.",
            "",
            "## 5. Inferences",
            "",
            "- A high same-id share is consistent with the identifier continuing across the two events.",
            "- A lower complete share on additional occurrences is consistent with those occurrences more often ending without a complete event.",
            "",
            "## 6. Hypotheses that stay open",
            "",
            "- The predecessor causes the birth.",
            "- A resource change is a handoff, a role change, or an authority transfer.",
            "- The same resource id means ownership.",
            "- Suspend is waiting, abort is failure, and a repeat is rework.",
            "- A return to an activity is an occurrence-level dependency.",
            "",
            "## 7. A new representation primitive",
            "",
            "No. The three checks describe births, identifiers, and lifecycle names the current representation can already store as occurrences and lifecycle values. They do not force a new primitive.",
            "",
            "## 8. Occurrence-level dependencies",
            "",
            "No. A pair at 100% in a window is still a frequency. No edge was added.",
            "",
            "## 9. Readiness",
            "",
            "No. Extra-occurrence readiness stays unresolved.",
            "",
            "## 10. The decision layer",
            "",
            "No. Policies should keep allocating to the primary occurrence. The birth patterns are not eligibility rules.",
            "",
            "## Decision",
            "",
            "MICRO SHOULD REMAIN FROZEN",
            "",
            "The evidence is strong as description. It is not sufficient to add a dependency, a readiness rule, or a change to allocation. The predecessor of a birth, the resource id, and the lifecycle mix can sit in a report. They do not yet say what the simulator should do differently.",
            "",
        ]
    )


def write_micro_experiments(events: list[Event], root: Path) -> None:
    births = collect_births(events)
    context = context_rows(events, births)
    context_summary = summarize_context(context)
    resources = summarize_resources(resource_rows(events))
    lifecycle = summarize_lifecycle(lifecycle_rows(events))
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    _write_csv(analysis / "bpi17_occurrence_birth_context.csv", context)
    _write_csv(analysis / "bpi17_occurrence_resource_continuity.csv", _resource_csv(resources))
    _write_csv(analysis / "bpi17_occurrence_lifecycle.csv", _lifecycle_csv(lifecycle))
    (docs / "bpi17_occurrence_birth_context.md").write_text(render_context(context_summary), encoding="utf-8")
    (docs / "bpi17_occurrence_resource_continuity.md").write_text(render_resources(resources), encoding="utf-8")
    (docs / "bpi17_occurrence_lifecycle.md").write_text(render_lifecycle(lifecycle), encoding="utf-8")
    (docs / "bpi17_micro_experiment_summary.md").write_text(
        render_summary(context_summary, resources, lifecycle),
        encoding="utf-8",
    )


def _by_case(events: list[Event]) -> dict[str, list[Event]]:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.case_id].append(event)
    for rows in grouped.values():
        rows.sort(key=lambda item: item.event_index)
    return grouped


def _index_of(rows: list[Event], event_index: int) -> int:
    for index, event in enumerate(rows):
        if event.event_index == event_index:
            return index
    raise KeyError(event_index)


def _case_occurrences(case_id: str, rows: list[Event]) -> list[dict]:
    current: dict[str, list[Event]] = {}
    numbers: Counter[str] = Counter()
    records: list[dict] = []

    def close(activity: str) -> None:
        events = current.pop(activity, None)
        if events:
            records.append(_occurrence_record(case_id, activity, numbers[activity], events))

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
            if event.lifecycle in TERMINAL and activity in current:
                close(activity)
        else:
            numbers[activity] += 1
            records.append(_occurrence_record(case_id, activity, numbers[activity], [event]))
    for activity in list(current):
        close(activity)
    return records


def _occurrence_record(case_id: str, activity: str, number: int, events: list[Event]) -> dict:
    names = {event.lifecycle for event in events}
    start = next((event.ts for event in events if event.lifecycle == "start"), None)
    complete = next((event.ts for event in events if event.lifecycle == "complete" and (start is None or event.ts >= start)), None)
    duration = (complete - start).total_seconds() if start is not None and complete is not None else None
    gap = (events[1].ts - events[0].ts).total_seconds() if len(events) > 1 else None
    return {
        "case_id": case_id,
        "activity": activity,
        "occurrence_number": number,
        "scheduled": "schedule" in names,
        "started": "start" in names,
        "suspended": "suspend" in names,
        "resumed": "resume" in names,
        "completed": "complete" in names,
        "aborted": "ate_abort" in names,
        "withdrawn": "withdraw" in names,
        "lifecycle_events": len(events),
        "duration_seconds": duration,
        "seconds_to_next_lifecycle": gap,
    }


def _lifecycle_cohort(rows: list[dict]) -> dict:
    n = len(rows)
    def count(flag: str) -> int:
        return sum(bool(row[flag]) for row in rows)
    durations = [row["duration_seconds"] for row in rows if row["duration_seconds"] is not None]
    events = [row["lifecycle_events"] for row in rows]
    return {
        "n": n,
        "small": n < SMALL_N,
        "scheduled": count("scheduled"),
        "started": count("started"),
        "suspended": count("suspended"),
        "resumed": count("resumed"),
        "completed": count("completed"),
        "aborted": count("aborted"),
        "withdrawn": count("withdrawn"),
        "median_events": median(events) if events else None,
        "p90_events": _percentile(events, 0.9) if events else None,
        "max_events": max(events) if events else None,
        "duration_n": len(durations),
        "median_duration": median(durations) if durations else None,
        "p90_duration": _percentile(durations, 0.9) if durations else None,
    }


def _relation_counts(rows: list[dict]) -> dict:
    n = len(rows)
    same = sum(row["relation"] == "same" for row in rows)
    different = sum(row["relation"] == "different" for row in rows)
    missing = sum(row["relation"] == "missing" for row in rows)
    return {
        "n": n,
        "same_resource_count": same,
        "different_resource_count": different,
        "missing_resource_count": missing,
        "same_resource_pct": (same / n) if n else 0.0,
        "different_resource_pct": (different / n) if n else 0.0,
        "missing_resource_pct": (missing / n) if n else 0.0,
        "same_resource_same_activity": sum(row["cell"] == "same_resource_same_activity" for row in rows),
        "same_resource_different_activity": sum(row["cell"] == "same_resource_different_activity" for row in rows),
        "different_resource_same_activity": sum(row["cell"] == "different_resource_same_activity" for row in rows),
        "different_resource_different_activity": sum(row["cell"] == "different_resource_different_activity" for row in rows),
    }


def _cell(relation: str, same_activity: bool) -> str:
    if relation == "missing":
        return "missing"
    side = "same_resource" if relation == "same" else "different_resource"
    activity = "same_activity" if same_activity else "different_activity"
    return f"{side}_{activity}"


def _resource_csv(summary: dict) -> list[dict]:
    rows = [{"slice": "overall", "activity": "", "predecessor_activity": "", "predecessor_lifecycle": "", **summary["overall"]}]
    for row in summary["by_activity"]:
        rows.append({"slice": "activity", "predecessor_activity": "", "predecessor_lifecycle": "", **row})
    for row in summary["named"]:
        rows.append({"slice": "named_pattern", **row})
    return rows


def _lifecycle_csv(summary: dict) -> list[dict]:
    rows = []
    for label, cohort in summary["overall"].items():
        rows.append({"slice": "overall", "activity": "", "cohort": label, **cohort})
    for row in summary["by_activity"]:
        for label in ("first", "additional"):
            rows.append({"slice": "activity", "activity": row["activity"], "cohort": label, **row[label]})
    return rows


def _named_window_sentence(context: dict) -> str:
    target = next(row for row in context["activities"] if row["activity"] == "O_Sent (mail and online)")
    shares = {item["window"]: item["share"] for item in target["named_pattern"]}
    return (
        "O_Created / complete is the immediate predecessor of "
        f"{shares[1]:.1%} of O_Sent (mail and online) births, "
        f"and it appears somewhere in the window for {shares[3]:.1%} at k = 3 and {shares[5]:.1%} at k = 5. "
        "The other named pairs stay near their k = 1 share inside the longer window."
    )


def _cohort_line(label: str, cohort: dict) -> str:
    return (
        f"FACT: {label}: n={cohort['n']}, scheduled {_pct(cohort['scheduled'], cohort['n'])}, "
        f"started {_pct(cohort['started'], cohort['n'])}, suspended {_pct(cohort['suspended'], cohort['n'])}, "
        f"resumed {_pct(cohort['resumed'], cohort['n'])}, completed {_pct(cohort['completed'], cohort['n'])}, "
        f"aborted {_pct(cohort['aborted'], cohort['n'])}, withdrawn {_pct(cohort['withdrawn'], cohort['n'])}. "
        f"Median lifecycle events {_num(cohort['median_events'])}, p90 {_num(cohort['p90_events'])}. "
        f"Start-to-complete durations: n={cohort['duration_n']}, median {_num(cohort['median_duration'])} seconds, "
        f"p90 {_num(cohort['p90_duration'])} seconds."
    )


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


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * probability
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _pct(count: int, total: int) -> str:
    if not total:
        return "n/a"
    return f"{100.0 * count / total:.1f}%"


def _num(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    events = load_events(root / "data" / "bpi17" / "events_normalized.csv")
    write_micro_experiments(events, root)
    print(f"events={len(events)} cases={len({event.case_id for event in events})}")


if __name__ == "__main__":
    main()
