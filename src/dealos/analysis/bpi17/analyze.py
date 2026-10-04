"""Recompute BPI17 structure from raw event fields.

Package columns such as resource_changed and candidate_dealos_element are not read.
A repeated activity is a new occurrence. Further lifecycle rows of an open
workflow occurrence are not counted as repetition.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median

from dealos.analysis.bpi17.read import Event


WORKFLOW = "Workflow"
TERMINAL = frozenset({"complete", "withdraw", "ate_abort"})
GAP_THRESHOLDS = (
    ("gt_1h", 3600),
    ("gt_4h", 4 * 3600),
    ("gt_8h", 8 * 3600),
    ("gt_24h", 24 * 3600),
    ("gt_72h", 72 * 3600),
)
DECISION_ACTIVITIES = (
    "A_Accepted",
    "A_Denied",
    "A_Cancelled",
    "O_Accepted",
    "O_Refused",
    "O_Cancelled",
)
RECURRING_CASE_SHARE = 0.5


def analyze_events(events: list[Event]) -> dict:
    by_case: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        by_case[event.case_id].append(event)

    store = _Store()
    case_rows = [_consume_case(case_id, rows, store) for case_id, rows in by_case.items()]
    n_cases = len(by_case)
    summary = _summary(n_cases, len(events), case_rows, store)
    return {
        "summary": summary,
        "cases": case_rows,
        "activities": _activity_rows(store.activity),
        "matrix": [
            {"resource": resource, "activity": name, "events": count}
            for (resource, name), count in sorted(store.matrix.items())
        ],
        "resources": _resource_summary(store.resource_events, store.resource_activities),
        "gaps": {
            "counts": dict(store.gap_counts),
            "resource_changes": dict(store.gap_resource_changes),
            "same_activity": dict(store.gap_same_activity),
            "edges": {name: _top_pairs(counter, 8) for name, counter in store.gap_edges.items()},
        },
        "workflow": {
            "variants": _top_sequences(store.workflow_variants, 8),
            "variant_count": len(store.workflow_variants),
            "full_variant_count": len(store.full_variants),
            "full_variants": _top_sequences(store.full_variants, 5),
            "dfg": _top_pairs(store.dfg, 15),
            "successors": {name: sorted(values) for name, values in sorted(store.successors.items())},
            "predecessors": {name: sorted(values) for name, values in sorted(store.predecessors.items())},
        },
        "fields": {
            "accepted": dict(store.accepted_values),
            "selected": dict(store.selected_values),
            "offered_amount_nonempty_events": sum(store.amount_values.values()),
            "offered_amount_values_capped": dict(store.amount_values.most_common(8)),
            "by_activity": {name: dict(counter) for name, counter in sorted(store.field_by_activity.items())},
            "offer_id_activities": dict(store.offer_activities),
        },
        "decisions": {
            "events": dict(store.decision_events),
            "cases": {name: len(cases) for name, cases in sorted(store.decision_cases.items())},
        },
        "durations_seconds": {
            "count": len(store.durations),
            "median": median(store.durations) if store.durations else None,
            "p90": _percentile(store.durations, 0.9) if store.durations else None,
        },
        "mismatches": _mismatches(summary),
    }


class _Store:
    def __init__(self) -> None:
        self.activity: dict[str, dict] = {}
        self.matrix: Counter[tuple[str, str]] = Counter()
        self.resource_events: Counter[str] = Counter()
        self.resource_activities: dict[str, Counter[str]] = defaultdict(Counter)
        self.lifecycle: Counter[str] = Counter()
        self.origin: Counter[str] = Counter()
        self.accepted_values: Counter[str] = Counter()
        self.selected_values: Counter[str] = Counter()
        self.amount_values: Counter[str] = Counter()
        self.field_by_activity: dict[str, Counter[str]] = defaultdict(Counter)
        self.offer_activities: Counter[str] = Counter()
        self.dfg: Counter[tuple[str, str]] = Counter()
        self.successors: dict[str, set[str]] = defaultdict(set)
        self.predecessors: dict[str, set[str]] = defaultdict(set)
        self.full_variants: Counter[tuple[str, ...]] = Counter()
        self.workflow_variants: Counter[tuple[str, ...]] = Counter()
        self.gap_edges: dict[str, Counter[tuple[str, str]]] = {name: Counter() for name, _ in GAP_THRESHOLDS}
        self.gap_resource_changes: Counter[str] = Counter()
        self.gap_same_activity: Counter[str] = Counter()
        self.gap_counts: Counter[str] = Counter()
        self.durations: list[float] = []
        self.reexec_cases: set[str] = set()
        self.reexec_cases_by_origin: dict[str, set[str]] = defaultdict(set)
        self.return_cases: set[str] = set()
        self.self_loop_cases: set[str] = set()
        self.overlap_cases: set[str] = set()
        self.decision_events: Counter[str] = Counter()
        self.decision_cases: dict[str, set[str]] = defaultdict(set)
        self.family_cases: dict[str, set[str]] = defaultdict(set)
        self.both_object_cases: set[str] = set()
        self.lifecycle_cases: dict[str, set[str]] = defaultdict(set)
        self.cases_with_offer_id: set[str] = set()
        self.cases_with_multiple_offers: set[str] = set()


def _consume_case(case_id: str, rows: list[Event], store: _Store) -> dict:
    rows.sort(key=lambda event: event.event_index)
    open_occurrence: set[str] = set()
    started: set[str] = set()
    occurrence_count: Counter[str] = Counter()
    opening_resource: dict[str, str] = {}
    start_ts: dict[str, object] = {}
    collapsed: list[str] = []
    offers: set[str] = set()
    resources: set[str] = set()
    origins: set[str] = set()
    adjacent = 0
    separated = 0
    resource_changes = 0
    same_activity_resource_changes = 0
    gap_hits = {name: 0 for name, _seconds in GAP_THRESHOLDS}
    overlap = False
    negative_gaps = 0
    previous: Event | None = None

    for event in rows:
        stats = _touch_activity(store.activity, event)
        store.matrix[(event.resource, event.activity)] += 1
        store.resource_events[event.resource] += 1
        store.resource_activities[event.resource][event.activity] += 1
        store.lifecycle[event.lifecycle] += 1
        store.origin[event.origin] += 1
        store.lifecycle_cases[event.lifecycle].add(case_id)
        store.family_cases[event.origin].add(case_id)
        resources.add(event.resource)
        origins.add(event.origin)
        if event.offer_id:
            offers.add(event.offer_id)
            store.offer_activities[event.activity] += 1
        _note_fields(store, event)
        if event.activity in DECISION_ACTIVITIES:
            store.decision_events[event.activity] += 1
            store.decision_cases[event.activity].add(case_id)

        if previous is not None:
            stats["arrivals"] += 1
            if event.resource != previous.resource:
                resource_changes += 1
                stats["resource_changes_into"] += 1
            if event.activity == previous.activity and event.resource != previous.resource:
                same_activity_resource_changes += 1
            delta = (event.ts - previous.ts).total_seconds()
            if delta < 0:
                negative_gaps += 1
            else:
                for name, threshold in GAP_THRESHOLDS:
                    if delta > threshold:
                        gap_hits[name] += 1
                        store.gap_counts[name] += 1
                        store.gap_edges[name][(previous.activity, event.activity)] += 1
                        if event.resource != previous.resource:
                            store.gap_resource_changes[name] += 1
                        if previous.activity == event.activity:
                            store.gap_same_activity[name] += 1

        if event.origin == WORKFLOW:
            overlap = _workflow_step(
                event,
                case_id,
                collapsed,
                open_occurrence,
                started,
                occurrence_count,
                opening_resource,
                start_ts,
                stats,
                store,
                overlap,
                previous,
            )
            if event.activity in occurrence_count and occurrence_count[event.activity] > 1 and _opened_now(event, previous):
                adjacent, separated = _count_repeat_shape(event, previous, opening_resource, stats, store, case_id, adjacent, separated)
        else:
            adjacent, separated = _object_step(
                event, case_id, occurrence_count, opening_resource, previous, stats, store, adjacent, separated
            )
        previous = event

    if "Application" in origins and "Offer" in origins:
        store.both_object_cases.add(case_id)
    if offers:
        store.cases_with_offer_id.add(case_id)
    if len(offers) > 1:
        store.cases_with_multiple_offers.add(case_id)
    _topology(case_id, collapsed, store)
    store.full_variants[tuple(event.activity for event in rows)] += 1
    store.workflow_variants[tuple(collapsed)] += 1
    duration_days = 0.0
    if len(rows) >= 2:
        duration_days = (rows[-1].ts - rows[0].ts).total_seconds() / 86400
    reexecutions = sum(count - 1 for count in occurrence_count.values() if count > 1)
    return {
        "case_id": case_id,
        "events": len(rows),
        "duration_days": round(duration_days, 6),
        "resources": len(resources),
        "reexecutions": reexecutions,
        "adjacent_reexecutions": adjacent,
        "separated_reexecutions": separated,
        "resource_changes": resource_changes,
        "same_activity_resource_changes": same_activity_resource_changes,
        "gaps_gt_1h": gap_hits["gt_1h"],
        "gaps_gt_4h": gap_hits["gt_4h"],
        "gaps_gt_8h": gap_hits["gt_8h"],
        "gaps_gt_24h": gap_hits["gt_24h"],
        "gaps_gt_72h": gap_hits["gt_72h"],
        "offers": len(offers),
        "open_overlap": int(overlap),
        "negative_gaps": negative_gaps,
    }


def _opened_now(event: Event, previous: Event | None) -> bool:
    if event.lifecycle == "schedule":
        return True
    return event.lifecycle == "start" and (previous is None or previous.activity != event.activity or previous.lifecycle not in {"schedule", "start"})


def _workflow_step(
    event, case_id, collapsed, open_occurrence, started, occurrence_count, opening_resource, start_ts, stats, store, overlap, previous
) -> bool:
    new_occurrence = event.lifecycle == "schedule" or (event.lifecycle == "start" and event.activity not in open_occurrence)
    if new_occurrence:
        occurrence_count[event.activity] += 1
        collapsed.append(event.activity)
        if occurrence_count[event.activity] > 1:
            store.reexec_cases.add(case_id)
            store.reexec_cases_by_origin[event.origin].add(case_id)
            stats["reexecutions"] += 1
            stats["cases_with_reexecution"].add(case_id)
            previous_resource = opening_resource.get(event.activity)
            if previous_resource == event.resource:
                stats["same_resource_reexecutions"] += 1
            elif previous_resource is not None:
                stats["different_resource_reexecutions"] += 1
        opening_resource[event.activity] = event.resource
        open_occurrence.add(event.activity)
        start_ts.pop(event.activity, None)
    if event.lifecycle == "start":
        if started - {event.activity}:
            overlap = True
            store.overlap_cases.add(case_id)
        started.add(event.activity)
        start_ts.setdefault(event.activity, event.ts)
    if event.lifecycle == "complete" and event.activity in start_ts:
        store.durations.append((event.ts - start_ts.pop(event.activity)).total_seconds())
    if event.lifecycle in TERMINAL:
        open_occurrence.discard(event.activity)
        started.discard(event.activity)
        if event.lifecycle != "complete":
            start_ts.pop(event.activity, None)
    return overlap


def _object_step(event, case_id, occurrence_count, opening_resource, previous, stats, store, adjacent, separated):
    occurrence_count[event.activity] += 1
    if occurrence_count[event.activity] == 1:
        opening_resource[event.activity] = event.resource
        return adjacent, separated
    store.reexec_cases.add(case_id)
    store.reexec_cases_by_origin[event.origin].add(case_id)
    stats["reexecutions"] += 1
    stats["cases_with_reexecution"].add(case_id)
    previous_resource = opening_resource[event.activity]
    if previous_resource == event.resource:
        stats["same_resource_reexecutions"] += 1
    else:
        stats["different_resource_reexecutions"] += 1
    opening_resource[event.activity] = event.resource
    if previous is not None and previous.activity == event.activity:
        adjacent += 1
        stats["adjacent_reexecutions"] += 1
    else:
        separated += 1
        stats["separated_reexecutions"] += 1
    return adjacent, separated


def _count_repeat_shape(event, previous, opening_resource, stats, store, case_id, adjacent, separated):
    if previous is not None and previous.activity == event.activity:
        adjacent += 1
        stats["adjacent_reexecutions"] += 1
    else:
        separated += 1
        stats["separated_reexecutions"] += 1
    return adjacent, separated


def _topology(case_id: str, collapsed: list[str], store: _Store) -> None:
    last_pos: dict[str, int] = {}
    for index, name in enumerate(collapsed):
        if index:
            pair = (collapsed[index - 1], name)
            store.dfg[pair] += 1
            store.successors[pair[0]].add(pair[1])
            store.predecessors[pair[1]].add(pair[0])
            if pair[0] == pair[1]:
                store.self_loop_cases.add(case_id)
        if name in last_pos and index - last_pos[name] > 1:
            store.return_cases.add(case_id)
        last_pos[name] = index


def _touch_activity(activity: dict[str, dict], event: Event) -> dict:
    stats = activity.get(event.activity)
    if stats is None:
        stats = {
            "activity": event.activity,
            "origin": event.origin,
            "events": 0,
            "cases": set(),
            "resources": set(),
            "lifecycle": Counter(),
            "reexecutions": 0,
            "cases_with_reexecution": set(),
            "adjacent_reexecutions": 0,
            "separated_reexecutions": 0,
            "same_resource_reexecutions": 0,
            "different_resource_reexecutions": 0,
            "resource_changes_into": 0,
            "arrivals": 0,
        }
        activity[event.activity] = stats
    stats["events"] += 1
    stats["cases"].add(event.case_id)
    stats["resources"].add(event.resource)
    stats["lifecycle"][event.lifecycle] += 1
    return stats


def _note_fields(store: _Store, event: Event) -> None:
    if event.accepted:
        store.accepted_values[event.accepted] += 1
        store.field_by_activity[event.activity]["accepted"] += 1
    if event.selected:
        store.selected_values[event.selected] += 1
        store.field_by_activity[event.activity]["selected"] += 1
    if event.offered_amount:
        store.amount_values[event.offered_amount] += 1
        store.field_by_activity[event.activity]["offered_amount"] += 1


def _activity_rows(activity: dict[str, dict]) -> list[dict]:
    rows = []
    for stats in sorted(activity.values(), key=lambda item: (-item["events"], item["activity"])):
        arrivals = stats["arrivals"]
        rows.append(
            {
                "activity": stats["activity"],
                "origin": stats["origin"],
                "events": stats["events"],
                "cases": len(stats["cases"]),
                "repeat_cases": len(stats["cases_with_reexecution"]),
                "reexecutions": stats["reexecutions"],
                "adjacent_reexecutions": stats["adjacent_reexecutions"],
                "separated_reexecutions": stats["separated_reexecutions"],
                "same_resource_reexecutions": stats["same_resource_reexecutions"],
                "different_resource_reexecutions": stats["different_resource_reexecutions"],
                "resource_change_rate_into": (stats["resource_changes_into"] / arrivals) if arrivals else 0.0,
                "distinct_resources": len(stats["resources"]),
                "lifecycle": dict(stats["lifecycle"]),
            }
        )
    return rows


def _resource_summary(resource_events: Counter[str], resource_activities: dict[str, Counter[str]]) -> dict:
    shares = []
    breadth = []
    concentrated = 0
    broad = 0
    for resource, events in resource_events.items():
        counts = resource_activities[resource]
        top = max(counts.values()) if counts else 0
        share = top / events if events else 0.0
        shares.append(share)
        breadth.append(len(counts))
        if share >= 0.8:
            concentrated += 1
        if len(counts) >= 5:
            broad += 1
    return {
        "resources": len(resource_events),
        "concentrated_resources": concentrated,
        "broad_resources": broad,
        "median_activity_share": median(shares) if shares else None,
        "median_activities_per_resource": median(breadth) if breadth else None,
    }


def _summary(n_cases, n_events, case_rows, store: _Store) -> dict:
    durations = [row["duration_days"] for row in case_rows]
    resource_counts = [row["resources"] for row in case_rows]
    event_counts = [row["events"] for row in case_rows]
    return {
        "cases": n_cases,
        "events": n_events,
        "activities": len(store.activity),
        "resources": len(store.resource_events),
        "median_events": median(event_counts) if event_counts else None,
        "p90_events": _percentile(event_counts, 0.9) if event_counts else None,
        "max_events": max(event_counts) if event_counts else 0,
        "median_resources": median(resource_counts) if resource_counts else None,
        "p90_resources": _percentile(resource_counts, 0.9) if resource_counts else None,
        "max_resources": max(resource_counts) if resource_counts else 0,
        "median_duration_days": median(durations) if durations else None,
        "p90_duration_days": _percentile(durations, 0.9) if durations else None,
        "max_duration_days": max(durations) if durations else 0,
        "cases_with_reexecution": len(store.reexec_cases),
        "reexecution_cases_by_origin": {name: len(cases) for name, cases in sorted(store.reexec_cases_by_origin.items())},
        "cases_with_return": len(store.return_cases),
        "cases_with_self_loop": len(store.self_loop_cases),
        "cases_with_overlap": len(store.overlap_cases),
        "cases_with_resource_change": sum(row["resource_changes"] > 0 for row in case_rows),
        "resource_change_events": sum(row["resource_changes"] for row in case_rows),
        "same_activity_resource_change_events": sum(row["same_activity_resource_changes"] for row in case_rows),
        "cases_with_same_activity_resource_change": sum(row["same_activity_resource_changes"] > 0 for row in case_rows),
        "negative_gaps": sum(row["negative_gaps"] for row in case_rows),
        "gap_case_counts": {
            name: sum(row[f"gaps_{name}"] > 0 for row in case_rows) for name, _seconds in GAP_THRESHOLDS
        },
        "gap_event_counts": dict(store.gap_counts),
        "lifecycle": dict(store.lifecycle),
        "lifecycle_cases": {name: len(cases) for name, cases in sorted(store.lifecycle_cases.items())},
        "origin": dict(store.origin),
        "family_cases": {name: len(cases) for name, cases in sorted(store.family_cases.items())},
        "cases_with_application_and_offer": len(store.both_object_cases),
        "cases_with_offer_id": len(store.cases_with_offer_id),
        "cases_with_multiple_offers": len(store.cases_with_multiple_offers),
        "complete_durations": len(store.durations),
        "cases_with_decision_activity": len(set().union(*store.decision_cases.values())) if store.decision_cases else 0,
    }


def _mismatches(summary: dict) -> list[dict]:
    n_cases = summary["cases"] or 1
    rows = [
        _mismatch(
            "M1",
            summary["cases_with_reexecution"],
            n_cases,
            "one-shot monotone task completion",
            "micro",
            "FACT",
            "A new occurrence of an activity inside the same case. Lifecycle rows of one workflow occurrence are excluded.",
        ),
        _mismatch(
            "M2",
            summary["cases_with_application_and_offer"],
            n_cases,
            "a single task DAG",
            "object",
            "FACT",
            "Application events and Offer events co-occur, and offers carry OfferID. The deal graph has no second object.",
        ),
        _mismatch(
            "M3",
            summary["gap_case_counts"].get("gt_24h", 0),
            n_cases,
            "a cause for unrecorded time",
            "temporal",
            "FACT",
            "A gap above 24 hours is observed. The log does not say whether it is internal work, an external wait, or time with no recorded event.",
            extension=False,
        ),
        _mismatch(
            "M4",
            summary["cases_with_resource_change"],
            n_cases,
            "named actor transitions",
            "macro",
            "INFERENCE",
            "Consecutive events name different org:resource values. That is not yet evidence of a handoff, a role, or authority.",
            extension=False,
        ),
        _mismatch(
            "M5",
            summary["lifecycle_cases"].get("suspend", 0),
            n_cases,
            "a single progress value in [0, 1]",
            "micro",
            "FACT",
            "Workflow events use suspend, resume, ate_abort, and withdraw. Those are not points on a monotone progress bar.",
        ),
        _mismatch(
            "M6",
            summary["cases_with_return"],
            n_cases,
            "an acyclic one-shot task graph",
            "micro",
            "FACT",
            "A workflow activity occurs, other workflow activities occur, and the first activity occurs again.",
        ),
        _mismatch(
            "M7",
            summary["cases_with_decision_activity"],
            n_cases,
            "a discrete authority grant",
            "macro",
            "HYPOTHESIS",
            "Accept, deny, refuse, and cancel appear as activity names. The log does not name who is allowed to decide.",
            extension=False,
        ),
        _mismatch(
            "M8",
            0,
            n_cases,
            "an information link between systems",
            "observation",
            "HYPOTHESIS",
            "No field records that one system's output is another system's input. Absence here is not evidence that the link exists.",
            extension=False,
        ),
    ]
    return rows


def _mismatch(identifier, count, n_cases, current_object, layer, status, note, extension=None) -> dict:
    share = count / n_cases if n_cases else 0.0
    recurring = share >= RECURRING_CASE_SHARE
    if extension is None:
        extension = recurring
    return {
        "id": identifier,
        "observed_count": count,
        "case_share": round(share, 4),
        "current_object": current_object,
        "layer": layer,
        "status": status,
        "recurring": recurring,
        "extension_candidate": bool(extension and recurring),
        "note": note,
    }


def _top_pairs(counter: Counter, limit: int) -> list[dict]:
    return [
        {"from": left, "to": right, "events": count}
        for (left, right), count in counter.most_common(limit)
    ]


def _top_sequences(counter: Counter, limit: int) -> list[dict]:
    rows = []
    for sequence, count in counter.most_common(limit):
        rows.append({"cases": count, "length": len(sequence), "sequence": list(sequence)})
    return rows


def _percentile(values, probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * probability
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight
