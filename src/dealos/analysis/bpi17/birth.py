"""What event immediately precedes a new occurrence.

A new occurrence uses the same rule as the BPI17 validation count: a later
workflow schedule or start, or a later application or offer completion.
The preceding event is recorded. It is not written as an edge.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from dealos.analysis.bpi17.read import Event, load_events

WORKFLOW = "Workflow"
# A single preceding pair must cover this share of an activity's births
# before it is named as a candidate. This is a reporting rule.
PAIR_SHARE = 0.5
# Activities with fewer births are listed and are not used to name a rule.
MIN_BIRTHS = 100


def collect_births(events: list[Event]) -> list[dict]:
    by_case: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        by_case[event.case_id].append(event)
    births: list[dict] = []
    for case_id, rows in by_case.items():
        rows.sort(key=lambda item: item.event_index)
        births.extend(_case_births(case_id, rows))
    return births


def summarize_births(births: list[dict]) -> dict:
    by_activity: dict[str, list[dict]] = defaultdict(list)
    for birth in births:
        by_activity[birth["activity"]].append(birth)
    activities = []
    for activity, rows in sorted(by_activity.items(), key=lambda item: -len(item[1])):
        pairs: Counter[tuple[str, str]] = Counter()
        same_resource = 0
        for row in rows:
            pairs[(row["predecessor_activity"], row["predecessor_lifecycle"])] += 1
            same_resource += int(row["same_resource"])
        top_pair, top_count = pairs.most_common(1)[0]
        share = top_count / len(rows)
        activities.append(
            {
                "activity": activity,
                "births": len(rows),
                "distinct_pairs": len(pairs),
                "top_predecessor_activity": top_pair[0],
                "top_predecessor_lifecycle": top_pair[1],
                "top_count": top_count,
                "top_share": round(share, 4),
                "same_resource": same_resource,
                "same_resource_share": round(same_resource / len(rows), 4),
                "candidate_pair": len(rows) >= MIN_BIRTHS and share >= PAIR_SHARE,
                "pairs": [
                    {
                        "predecessor_activity": left,
                        "predecessor_lifecycle": right,
                        "count": count,
                    }
                    for (left, right), count in pairs.most_common()
                ],
            }
        )
    frequent = [row for row in activities if row["births"] >= MIN_BIRTHS]
    return {
        "births": len(births),
        "pair_share_rule": PAIR_SHARE,
        "min_births": MIN_BIRTHS,
        "activities": activities,
        "frequent_activities": len(frequent),
        "activities_with_a_dominant_pair": sum(row["candidate_pair"] for row in frequent),
    }


def _case_births(case_id: str, rows: list[Event]) -> list[dict]:
    open_occurrence: set[str] = set()
    counts: Counter[str] = Counter()
    births: list[dict] = []
    previous: Event | None = None
    for event in rows:
        opened = False
        if event.origin == WORKFLOW:
            opened = event.lifecycle == "schedule" or (
                event.lifecycle == "start" and event.activity not in open_occurrence
            )
            if opened:
                counts[event.activity] += 1
                open_occurrence.add(event.activity)
            if event.lifecycle in {"complete", "withdraw", "ate_abort"}:
                open_occurrence.discard(event.activity)
        else:
            counts[event.activity] += 1
            opened = True
        if opened and counts[event.activity] > 1 and previous is not None:
            births.append(
                {
                    "case_id": case_id,
                    "event_index": event.event_index,
                    "activity": event.activity,
                    "lifecycle": event.lifecycle,
                    "predecessor_activity": previous.activity,
                    "predecessor_lifecycle": previous.lifecycle,
                    "same_resource": previous.resource == event.resource,
                }
            )
        previous = event
    return births


def render_birth_report(summary: dict) -> str:
    frequent = [row for row in summary["activities"] if row["births"] >= summary["min_births"]]
    lines = [
        "# BPI17 occurrence birth",
        "",
        "A birth is a new occurrence of an activity that already occurred in the same case. Workflow births are a later schedule, or a start when that activity is not already open. Application and offer births are a later completion of the same activity name. The row recorded here is only the event immediately before that birth.",
        "",
        f"FACT: {summary['births']} births.",
        f"A preceding pair is called dominant when it covers at least {summary['pair_share_rule']:.0%} of an activity's births and that activity has at least {summary['min_births']} births. That bar is a reporting rule. It is not a significance test, and a dominant pair is not an edge.",
        "",
        "| Activity | Births | Distinct pairs | Top predecessor | Top lifecycle | Top share | Same resource |",
        "| --- | ---: | ---: | --- | --- | ---: | ---: |",
    ]
    for row in frequent:
        lines.append(
            f"| {row['activity']} | {row['births']} | {row['distinct_pairs']} | {row['top_predecessor_activity']} | {row['top_predecessor_lifecycle']} | {row['top_share']:.1%} | {row['same_resource_share']:.1%} |"
        )
    lines.append("")
    named = [row for row in frequent if row["candidate_pair"]]
    scattered = [row["activity"] for row in frequent if not row["candidate_pair"]]
    same_activity = [row for row in named if row["top_predecessor_activity"] == row["activity"]]
    other_activity = [row for row in named if row["top_predecessor_activity"] != row["activity"]]
    if not named:
        lines.append(
            f"FACT: none of the {len(frequent)} activities with at least {summary['min_births']} births has one preceding pair covering half of its births."
        )
    else:
        lines.append(
            f"FACT: {len(named)} of {len(frequent)} frequent activities have a dominant preceding pair. "
            f"The others are {', '.join(scattered) if scattered else 'none'}."
        )
        if same_activity:
            lines.append(
                "The dominant pair is the same activity for "
                + ", ".join(f"{row['activity']} ({row['top_share']:.1%})" for row in same_activity)
                + ". The new occurrence opens after another event of that same activity."
            )
        if other_activity:
            lines.append(
                "The dominant pair is a different activity for "
                + ", ".join(
                    f"{row['activity']} after {row['top_predecessor_activity']} / {row['top_predecessor_lifecycle']} ({row['top_share']:.1%})"
                    for row in other_activity
                )
                + "."
            )
    lines.append(
        "No pair is written as an edge. Extra-occurrence readiness stays unresolved. "
        "The decision layer should keep allocating to the primary occurrence only."
    )
    lines.append("")
    lines.append("Same-resource share is a count of identical resource ids. It is not a handoff.")
    lines.append("This pass does not interpret gaps, authority, information links, or deal completion.")
    return "\n".join(lines) + "\n"


def write_birth(events: list[Event], root: Path) -> dict:
    births = collect_births(events)
    summary = summarize_births(births)
    analysis = root / "analysis"
    docs = root / "docs"
    analysis.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "activity",
        "births",
        "distinct_pairs",
        "top_predecessor_activity",
        "top_predecessor_lifecycle",
        "top_count",
        "top_share",
        "same_resource",
        "same_resource_share",
        "candidate_pair",
    ]
    with (analysis / "bpi17_occurrence_birth.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary["activities"])
    (docs / "bpi17_occurrence_birth.md").write_text(render_birth_report(summary), encoding="utf-8")
    return summary


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    summary = write_birth(load_events(root / "data" / "bpi17" / "events_normalized.csv"), root)
    print(
        f"births={summary['births']} frequent={summary['frequent_activities']} "
        f"dominant={summary['activities_with_a_dominant_pair']}"
    )


if __name__ == "__main__":
    main()
