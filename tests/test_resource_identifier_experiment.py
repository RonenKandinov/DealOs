"""R0 versus a persistent resource identifier. The micro classes stay unchanged."""

from dataclasses import fields
from datetime import datetime, timedelta

from dealos.analysis.bpi17.read import Event
from dealos.analysis.bpi17.resource_identifier_experiment import (
    DECISION_JUSTIFIED,
    DECISION_NOT_JUSTIFIED,
    R0_OCCURRENCE_FIELDS,
    R0_RESOURCE_FIELDS,
    R1_ASSOCIATION_FIELDS,
    R1_IDENTIFIER_FIELDS,
    PersistentResourceIdentifier,
    ResourceOccurrenceAssociation,
    analyze_identifier,
    render_report,
)
from dealos.domain.models import Resource, TaskOccurrence


def test_micro_fields_stay_the_frozen_lists() -> None:
    assert tuple(field.name for field in fields(TaskOccurrence)) == R0_OCCURRENCE_FIELDS
    assert tuple(field.name for field in fields(Resource)) == R0_RESOURCE_FIELDS
    assert tuple(field.name for field in fields(PersistentResourceIdentifier)) == R1_IDENTIFIER_FIELDS
    assert tuple(field.name for field in fields(ResourceOccurrenceAssociation)) == R1_ASSOCIATION_FIELDS


def test_one_identifier_covers_two_cases_and_r0_has_no_query() -> None:
    start = datetime(2016, 1, 1, 9, 0)
    events = [
        _event("c1", 1, start, "W_Call", "Workflow", "User_1", "schedule"),
        _event("c1", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_1", "start"),
        _event("c1", 3, start + timedelta(minutes=2), "W_Call", "Workflow", "User_2", "complete"),
        _event("c2", 1, start, "A_Concept", "Application", "User_1", "complete"),
        _event("c2", 2, start + timedelta(minutes=1), "A_Concept", "Application", "", "complete"),
    ]
    summary = analyze_identifier(events)
    user_1 = summary["queries"]["User_1"]
    user_2 = summary["queries"]["User_2"]
    assert summary["r0_query_result"] is None
    assert user_1["cases"] == {"c1", "c2"}
    assert user_1["activities"] == {"W_Call", "A_Concept"}
    assert user_1["occurrence_count"] == 2
    assert user_1["events"] == 3
    assert user_2["cases"] == {"c1"}
    assert user_2["occurrence_count"] == 1
    assert user_2["events"] == 1
    assert summary["identifiers"] == 2
    assert summary["blank_events"] == 1
    assert summary["occurrences_with_several_identifiers"] == 1
    assert summary["associations"] == 3
    assert summary["transition_pairs"] == 0
    assert summary["cross_case_identifiers"] == 1
    assert summary["faithful"] is True
    assert summary["decision"] == DECISION_JUSTIFIED
    names = {row["name"] for row in summary["capabilities"]}
    assert names == {"Cross-case identity", "Resource-occurrence association", "Persistence queries"}
    assert all(row["r1"] and not row["r0"] for row in summary["capabilities"])


def test_a_single_case_log_does_not_justify_the_primitive() -> None:
    start = datetime(2016, 4, 1, 9, 0)
    events = [
        _event("c1", 1, start, "W_Call", "Workflow", "User_1", "schedule"),
        _event("c1", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_1", "complete"),
    ]
    summary = analyze_identifier(events)
    assert summary["cross_case_identifiers"] == 0
    assert summary["decision"] == DECISION_NOT_JUSTIFIED


def test_a_later_schedule_is_a_second_occurrence_inside_the_case() -> None:
    start = datetime(2016, 5, 1, 9, 0)
    events = [
        _event("c", 1, start, "W_Call", "Workflow", "User_1", "schedule"),
        _event("c", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_1", "start"),
        _event("c", 3, start + timedelta(minutes=2), "W_Call", "Workflow", "User_1", "suspend"),
        _event("c", 4, start + timedelta(minutes=3), "W_Call", "Workflow", "User_1", "complete"),
        _event("c", 5, start + timedelta(minutes=4), "W_Call", "Workflow", "User_9", "schedule"),
        _event("c", 6, start + timedelta(minutes=5), "W_Call", "Workflow", "User_9", "ate_abort"),
    ]
    summary = analyze_identifier(events)
    assert summary["occurrences"] == 2
    assert summary["queries"]["User_1"]["occurrence_count"] == 1
    assert summary["queries"]["User_1"]["events"] == 4
    assert summary["queries"]["User_9"]["occurrence_count"] == 1
    assert summary["queries"]["User_9"]["events"] == 2
    assert summary["occurrences_with_several_identifiers"] == 0
    text = render_report(summary)
    assert text.strip().splitlines()[-1] == DECISION_NOT_JUSTIFIED


def test_case_boundary_keeps_the_identifier_on_its_own_case() -> None:
    start = datetime(2016, 6, 1, 9, 0)
    events = [
        _event("c1", 1, start, "W_Call", "Workflow", "User_1", "schedule"),
        _event("c1", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_1", "complete"),
        _event("c2", 1, start, "W_Call", "Workflow", "User_9", "schedule"),
        _event("c2", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_9", "complete"),
    ]
    summary = analyze_identifier(events)
    assert summary["queries"]["User_1"]["cases"] == {"c1"}
    assert summary["queries"]["User_9"]["cases"] == {"c2"}
    assert summary["decision"] == DECISION_NOT_JUSTIFIED


def _event(case_id, index, ts, activity, origin, resource, lifecycle):
    return Event(
        case_id=case_id,
        event_index=index,
        ts=ts,
        activity=activity,
        action="",
        origin=origin,
        resource=resource,
        lifecycle=lifecycle,
        offer_id="",
        accepted="",
        selected="",
        offered_amount="",
    )
