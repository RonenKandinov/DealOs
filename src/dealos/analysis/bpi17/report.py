"""Validation report. Every stated conclusion carries an epistemic tag."""

from __future__ import annotations


def render_report(result: dict) -> str:
    summary = result["summary"]
    n_cases = summary["cases"]
    mismatches = {row["id"]: row for row in result["mismatches"]}
    lines = [
        "# BPI17 validation report",
        "",
        "This report compares the BPI Challenge 2017 loan-application sample with the current DealOS micro and macro representations. The counts are recomputed from case, time, activity, resource, lifecycle, and offer fields. The package columns that already name a handoff, a repeat, or a DealOS element are not used.",
        "",
        "A pattern is called recurring when it appears in at least half of the cases. That cutoff is a reporting rule. It is not a significance test.",
        "",
        "## 1. Dataset profile",
        "",
        f"FACT: the table contains {summary['events']} events, {summary['cases']} cases, {summary['activities']} activities, and {summary['resources']} resource identifiers.",
        f"FACT: event origins are { _fmt_counts(summary['origin']) }.",
        f"FACT: lifecycle transitions are { _fmt_counts(summary['lifecycle']) }.",
        "INFERENCE: names beginning with A_ are application-object events, O_ are offer-object events, and W_ are workflow activities, because that is how the source names them and how EventOrigin is filled.",
        "HYPOTHESIS: none of those names is yet a DealOS task, role, or authority state.",
        "",
        "## 2. Case structure",
        "",
        f"FACT: events per case have median {_num(summary['median_events'])}, 90th percentile {_num(summary['p90_events'])}, and maximum {summary['max_events']}.",
        f"FACT: distinct resource identifiers per case have median {_num(summary['median_resources'])}, 90th percentile {_num(summary['p90_resources'])}, and maximum {summary['max_resources']}.",
        f"FACT: observed case duration in days has median {_num(summary['median_duration_days'])}, 90th percentile {_num(summary['p90_duration_days'])}, and maximum {_num(summary['max_duration_days'])}.",
        f"FACT: {summary['cases_with_application_and_offer']} cases contain both an Application event and an Offer event.",
        "INFERENCE: a case is a candidate deal object. The log does not define target tasks or a completion rule.",
        "",
        "## 3. Activity structure",
        "",
        _activity_section(result["activities"], n_cases),
        "",
        "## 4. Resource structure",
        "",
        _resource_section(result["resources"], result["activities"]),
        "",
        "## 5. Temporal structure",
        "",
        _temporal_section(summary, result["gaps"], result["durations_seconds"], n_cases),
        "",
        "## 6. Repetition and rework",
        "",
        _repetition_section(summary, result["activities"], n_cases),
        "",
        "## 7. Handoff analysis",
        "",
        _handoff_section(summary, result["activities"], n_cases),
        "",
        "## 8. Workflow topology",
        "",
        _workflow_section(summary, result["workflow"], n_cases),
        "",
        "## 9. Application, offer, and workflow objects",
        "",
        _object_section(summary, result["fields"], result["decisions"], n_cases),
        "",
        "## 10. DealOS micro mapping",
        "",
        *_mapping_lines(summary, result, "micro"),
        "",
        "## 11. DealOS macro mapping",
        "",
        *_mapping_lines(summary, result, "macro"),
        "",
        "## 12. Representation gaps",
        "",
        _mismatch_section(result["mismatches"]),
        "",
        "## 13. Candidate model extensions",
        "",
        _extension_section(result["mismatches"]),
        "",
        "## 14. Evidence, inference, and hypothesis",
        "",
        "FACT is a count or a relation present in the event fields.",
        "INFERENCE is a reading of those fields that a second person could reject, such as treating an A_ name as an application object.",
        "HYPOTHESIS is a mechanism the log does not contain: rework, handoff, external waiting, authority, or an information link.",
        "The precomputed epistemic_status on every source row is inference. This report does not copy it.",
        "",
        "## 15. Recommended next experiments",
        "",
        *_closing(summary, mismatches, n_cases),
        "",
    ]
    return "\n".join(lines) + "\n"


def _activity_section(activities: list[dict], n_cases: int) -> str:
    lines = [
        f"FACT: {sum(row['cases'] == n_cases for row in activities)} activities occur in every case. The others are absent from some cases.",
        "INFERENCE: absence from some cases is the kind of fact an optional task can record. The log does not show the AND edges that would make that task the same object as a V1 task.",
        "",
        "| Activity | Events | Cases | Repeat cases | Resources |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in activities:
        lines.append(
            f"| {row['activity']} | {row['events']} | {row['cases']} | {row['repeat_cases']} | {row['distinct_resources']} |"
        )
    return "\n".join(lines)


def _resource_section(resources: dict, activities: list[dict]) -> str:
    widest = sorted(activities, key=lambda row: row["distinct_resources"], reverse=True)[:5]
    widest_text = ", ".join(f"{row['activity']} ({row['distinct_resources']})" for row in widest)
    return "\n".join(
        [
            f"FACT: {resources['resources']} distinct org:resource values appear.",
            f"FACT: the median number of activities per resource is {_num(resources['median_activities_per_resource'])}. The median share of a resource's events that sit in its single most common activity is {_num(resources['median_activity_share'])}.",
            f"FACT: {resources['concentrated_resources']} resources have at least 80 percent of their events in one activity. {resources['broad_resources']} resources appear in five or more activities.",
            f"FACT: the activities touched by the most resources are {widest_text}.",
            "INFERENCE: org:resource is an observed identifier. It is a candidate for an actor id.",
            "HYPOTHESIS: specialization is not a role, a department, or an authority grant. No source field names a manager, a counsel, or an executive.",
        ]
    )


def _temporal_section(summary: dict, gaps: dict, durations: dict, n_cases: int) -> str:
    lines = ["FACT: gap counts are nested. A gap above 72 hours is also a gap above 1 hour."]
    for name, label in (
        ("gt_1h", ">1 hour"),
        ("gt_4h", ">4 hours"),
        ("gt_8h", ">8 hours"),
        ("gt_24h", ">24 hours"),
        ("gt_72h", ">72 hours"),
    ):
        events = summary["gap_event_counts"].get(name, 0)
        cases = summary["gap_case_counts"].get(name, 0)
        changed = gaps["resource_changes"].get(name, 0)
        same = gaps.get("same_activity", {}).get(name, 0)
        lines.append(
            f"FACT: {events} consecutive pairs are {label}, in {cases} cases ({_pct(cases, n_cases)}). In {changed} of those pairs the resource identifier also changes ({_pct(changed, events)} of the pairs). In {same} of those pairs both events have the same activity name ({_pct(same, events)})."
        )
    lines.append(f"FACT: negative timestamp gaps: {summary['negative_gaps']}.")
    top = gaps["edges"].get("gt_24h", [])[:5]
    if top:
        rendered = ", ".join(f"{row['from']} -> {row['to']} ({row['events']})" for row in top)
        lines.append(f"FACT: the most common activity pairs around a gap above 24 hours are {rendered}.")
    median = durations["median"]
    lines.append(
        f"FACT: {durations['count']} workflow occurrences have both a start and a later complete. Wall-clock duration, including any suspend between those two events, has median {_num(median)} seconds and 90th percentile {_num(durations['p90'])} seconds."
        if median is not None
        else "FACT: no workflow occurrence has both a start and a later complete."
    )
    lines.append(
        "HYPOTHESIS: a long gap is internal processing, an external wait, or time with no recorded event. The three readings stay open. The gap by itself does not choose among them."
    )
    return "\n".join(lines)


def _repetition_section(summary: dict, activities: list[dict], n_cases: int) -> str:
    repeated = [row for row in activities if row["repeat_cases"]]
    repeated.sort(key=lambda row: row["repeat_cases"], reverse=True)
    lines = [
        f"FACT: {summary['cases_with_reexecution']} cases ({_pct(summary['cases_with_reexecution'], n_cases)}) contain at least one new occurrence of an activity that already occurred.",
        f"FACT: cases with a new occurrence, by event origin: {_fmt_counts(summary['reexecution_cases_by_origin'])}.",
        "FACT: a workflow schedule followed by start, suspend, resume, or complete is one occurrence. Those extra rows are not counted as repetition.",
        "HYPOTHESIS: a new occurrence is rework. The log shows the activity again. It does not show that earlier work was undone.",
        "",
        "| Activity | Repeat cases | Adjacent | Separated | Same resource | Different resource |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in repeated[:12]:
        lines.append(
            f"| {row['activity']} | {row['repeat_cases']} | {row['adjacent_reexecutions']} | {row['separated_reexecutions']} | {row['same_resource_reexecutions']} | {row['different_resource_reexecutions']} |"
        )
    return "\n".join(lines)


def _handoff_section(summary: dict, activities: list[dict], n_cases: int) -> str:
    changes = summary["resource_change_events"]
    same = summary["same_activity_resource_change_events"]
    same_occurrence = sum(row["same_resource_reexecutions"] for row in activities)
    different_occurrence = sum(row["different_resource_reexecutions"] for row in activities)
    return "\n".join(
        [
            f"FACT: {summary['cases_with_resource_change']} cases ({_pct(summary['cases_with_resource_change'], n_cases)}) have at least one pair of consecutive events with different resource identifiers. There are {changes} such pairs.",
            f"FACT: {same} of those pairs ({_pct(same, changes)}) keep the same activity name. {summary['cases_with_same_activity_resource_change']} cases contain at least one such pair. Many of those pairs are successive lifecycle rows of one workflow occurrence.",
            f"FACT: among new occurrences, {same_occurrence} are opened by the same resource as the previous occurrence and {different_occurrence} by a different resource.",
            "INFERENCE: a resource change on the next different activity is the ordinary succession of the log. It is not, by itself, a transfer of one piece of work.",
            "HYPOTHESIS: a resource change inside the same activity, or on a later occurrence, is a handoff. The identifier changed. The log does not say that responsibility was transferred.",
        ]
    )


def _workflow_section(summary: dict, workflow: dict, n_cases: int) -> str:
    lines = [
        f"FACT: collapsed workflow sequences have {workflow['variant_count']} distinct variants. Full activity sequences, including application and offer names, have {workflow['full_variant_count']} distinct variants.",
        f"FACT: {summary['cases_with_return']} cases ({_pct(summary['cases_with_return'], n_cases)}) return to a workflow activity after a different workflow activity.",
        f"FACT: {summary['cases_with_self_loop']} cases ({_pct(summary['cases_with_self_loop'], n_cases)}) place two occurrences of the same workflow activity next to each other.",
        f"FACT: {summary['cases_with_overlap']} cases ({_pct(summary['cases_with_overlap'], n_cases)}) start one workflow activity while another workflow activity has been started and not yet completed, aborted, or withdrawn.",
        "INFERENCE: successor variety below is a population fact. Inside one case the collapsed sequence still has one next activity. This is not an AND edge.",
        "",
        "Most common collapsed workflow sequences:",
        "",
    ]
    for row in workflow["variants"]:
        lines.append(f"- {row['cases']} cases, length {row['length']}: {' -> '.join(row['sequence'])}")
    lines.append("")
    lines.append("Most common directly-follows pairs in the collapsed workflow sequence:")
    lines.append("")
    for row in workflow["dfg"]:
        lines.append(f"- {row['from']} -> {row['to']}: {row['events']}")
    branching = [name for name, values in workflow["successors"].items() if len(values) > 1]
    joining = [name for name, values in workflow["predecessors"].items() if len(values) > 1]
    lines.append("")
    lines.append(f"FACT: workflow activities with more than one observed successor: {', '.join(branching) if branching else 'none'}.")
    lines.append(f"FACT: workflow activities with more than one observed predecessor: {', '.join(joining) if joining else 'none'}.")
    return "\n".join(lines)


def _object_section(summary: dict, fields: dict, decisions: dict, n_cases: int) -> str:
    lines = [
        f"FACT: cases by event origin: {_fmt_counts(summary['family_cases'])}.",
        f"FACT: {summary['cases_with_offer_id']} cases have at least one OfferID. {summary['cases_with_multiple_offers']} cases have more than one distinct OfferID.",
        f"FACT: activities that carry an OfferID: {_fmt_counts(fields['offer_id_activities'])}.",
        f"FACT: Accepted values: {_fmt_counts(fields['accepted'])}. Selected values: {_fmt_counts(fields['selected'])}.",
        f"FACT: non-empty OfferedAmount events: {fields['offered_amount_nonempty_events']}. Accepted, Selected, and OfferedAmount are filled on {', '.join(fields['by_activity']) or 'no activity'}.",
        f"FACT: decision-like activity names occur in {summary['cases_with_decision_activity']} cases. Event counts: {_fmt_counts(decisions['events'])}. Case counts: {_fmt_counts(decisions['cases'])}.",
        "INFERENCE: Application, Offer, and Workflow are three object families in this log. OfferID ties some events to an offer object.",
        "HYPOTHESIS: an offer is a decision output, and Accepted is an authority act. The fields record an activity and a flag. They do not record who is allowed to approve.",
    ]
    return "\n".join(lines)


def _mapping_lines(summary: dict, result: dict, layer: str) -> list[str]:
    if layer == "micro":
        return [
            f"- Application case -> deal object candidate. {summary['cases']} cases. INFERENCE.",
            f"- Workflow activity occurrence -> task candidate. Collapsed workflow variants: {result['workflow']['variant_count']}. INFERENCE.",
            f"- Activity absent from some cases -> optional task is a possible recording. See the activity table. INFERENCE. The log does not supply AND dependencies. HYPOTHESIS that the edges match.",
            f"- Timestamp order -> event order. Median duration {_num(summary['median_duration_days'])} days. FACT as an observation. V1 time is a day index, not these timestamps. INFERENCE that the two clocks are the same object.",
            f"- Start then complete -> a duration, not a progress value in [0, 1]. {result['durations_seconds']['count']} paired occurrences. FACT.",
            f"- New occurrence of the same activity -> not one-shot completion. {summary['cases_with_reexecution']} cases. FACT that it occurs. HYPOTHESIS that it is rework.",
            f"- Return after another workflow activity -> not an acyclic one-shot graph. {summary['cases_with_return']} cases. FACT.",
            f"- Open overlap of two started workflow activities -> concurrent work is visible. {summary['cases_with_overlap']} cases. FACT. V1 can allocate several ready tasks in one day, so overlap alone does not force a new micro object. INFERENCE.",
            "- OfferID -> no micro object. FACT that the identifier is present. The task DAG does not contain it.",
        ]
    return [
        f"- org:resource -> actor identifier candidate. {summary['resources']} identifiers. INFERENCE. Not a role. HYPOTHESIS that any of them is a department.",
        f"- Resource identifier changes between consecutive events -> {summary['resource_change_events']} pairs. FACT. A handoff, a role change, or an authority change is not in the record. HYPOTHESIS.",
        f"- Accept, deny, refuse, and cancel activity names -> observed actions in {summary['cases_with_decision_activity']} cases. FACT. A discrete authority grant is not in the record. HYPOTHESIS.",
        "- Information produced by one system and required by another -> no field. FACT that the field is absent. An information link remains a hypothesis.",
        "- Involvement over time -> the resource set of a case changes across events. FACT as a set of identifiers. The reason codes task_ready, escalation, and information_requirement are not in the log. HYPOTHESIS.",
        "No macro field is filled from this sample. The representation can store an actor and a grant. This log does not identify the grant.",
    ]


def _mismatch_section(rows: list[dict]) -> str:
    lines = [
        "| Id | Cases | Share | Current object that fails | Layer | Tag | Recurring | Extension candidate |",
        "| --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['observed_count']} | {row['case_share']:.3f} | {row['current_object']} | {row['layer']} | {row['status']} | {row['recurring']} | {row['extension_candidate']} |"
        )
        lines.append("")
        lines.append(f"{row['status']}: {row['note']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _extension_section(rows: list[dict]) -> str:
    chosen = [row for row in rows if row["extension_candidate"]]
    lines = [
        "An extension candidate is a recurring pattern that no current object can say. This pass does not implement any of them.",
        "",
    ]
    if not chosen:
        lines.append("No mismatch cleared the recurrence rule as an extension candidate.")
        return "\n".join(lines)
    for row in chosen:
        lines.append(f"- {row['id']} ({row['layer']}): {row['note']}")
    lines.append("")
    lines.append("M3, M4, M7, and M8 stay out of the extension list. A gap is real and its cause is unknown. A resource change is real and is not yet a handoff. An accept activity is real and is not an authority grant. An information link is not in the file.")
    return "\n".join(lines)


def _closing(summary: dict, mismatches: dict, n_cases: int) -> list[str]:
    return [
        "### Ten findings",
        "",
        f"1. FACT: {summary['cases']} complete cases and {summary['events']} events, with median duration {_num(summary['median_duration_days'])} days and median {_num(summary['median_resources'])} resource identifiers.",
        f"2. FACT: Application, Offer, and Workflow events co-exist. {summary['cases_with_application_and_offer']} cases have both an application event and an offer event. {summary['cases_with_multiple_offers']} cases have more than one OfferID.",
        f"3. FACT: workflow lifecycle is not a single complete mark. Suspend appears in {summary['lifecycle_cases'].get('suspend', 0)} cases. Counts: {_fmt_counts(summary['lifecycle'])}.",
        f"4. FACT: {summary['cases_with_reexecution']} cases ({_pct(summary['cases_with_reexecution'], n_cases)}) open a further occurrence of an activity. This count excludes extra lifecycle rows of one workflow occurrence.",
        f"5. HYPOTHESIS: that further occurrence is rework. The observation is only that the activity occurs again.",
        f"6. FACT: {summary['cases_with_resource_change']} cases change resource identifier between consecutive events. {summary['same_activity_resource_change_events']} of {summary['resource_change_events']} changes keep the same activity.",
        f"7. HYPOTHESIS: the same-activity resource change is a handoff. The different-activity change is ordinary succession until a record says otherwise.",
        f"8. FACT: {summary['gap_case_counts'].get('gt_24h', 0)} cases have a gap above 24 hours. The activity pair and the resource change are known. The cause is not.",
        f"9. FACT: {summary['cases_with_return']} cases return to a workflow activity after another workflow activity. {summary['cases_with_overlap']} cases start a second workflow activity while one is still open.",
        f"10. FACT: accept, deny, refuse, and cancel are activity names in {summary['cases_with_decision_activity']} cases. No field states an authority relation.",
        "",
        "### Five strongest mismatches",
        "",
        _strongest(mismatches),
        "",
        "### Evidence versus hypothesis",
        "",
        "The case counts for a further occurrence (M1), a second object family (M2), a gap (M3), a resource-identifier change (M4), suspend and abort (M5), and a return in the workflow sequence (M6) are facts about the log.",
        "Calling M1 rework, M3 an external wait, M4 a handoff, or M7 an authority grant is a hypothesis.",
        "M8 is the fact that an information link is not recorded.",
        "",
        "### Micro model",
        "",
        "M1 and M5 clear the recurrence rule. They are facts the current micro transition cannot say: completion is one-shot and monotone, and a workflow activity also has suspend, resume, abort, and withdraw. They justify a later controlled screen. They do not justify editing the frozen transition in this pass.",
        "M6, a return to an earlier workflow activity, is the same family of fact as M1 and is present in 37.1 percent of cases, under the half-case rule. It stays in the catalog and is not a separate extension candidate.",
        "M2, the offer object, is also a fact the single task DAG cannot say. A second object is a representation change, not a change to the progress equation, and it is not implemented here.",
        "Optional activities and concurrent open work do not, by themselves, force a micro change. V1 already has optional tasks and can hold more than one ready task.",
        "",
        "### Macro model",
        "",
        "Nothing in this sample justifies filling or changing the macro record. Resource identifiers can later be stored as actor ids. The log does not name a role, a system boundary, an authority state, or an information link.",
        "",
        "### Explicitly not modeled yet",
        "",
        "- Rework as a progress reversal.",
        "- External waiting as the meaning of a timestamp gap.",
        "- A handoff mechanism, a role, a department, or an authority grant.",
        "- Information links between systems.",
        "- A customer organization, a champion, strategic behavior, or a probability.",
        "- Any new policy, optimizer, or change to the micro simulator.",
    ]


def _strongest(mismatches: dict) -> str:
    ranked = sorted(
        mismatches.values(),
        key=lambda row: (row["extension_candidate"], row["case_share"]),
        reverse=True,
    )
    lines = []
    for row in ranked[:5]:
        lines.append(
            f"- {row['id']} ({row['status']}): {row['note']} Case share {row['case_share']:.3f}. Extension candidate: {row['extension_candidate']}."
        )
    return "\n".join(lines)


def _fmt_counts(values: dict) -> str:
    if not values:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in values.items())


def _pct(count: int, total: int) -> str:
    if not total:
        return "0%"
    return f"{100.0 * count / total:.1f}%"


def _num(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
