"""The BPI17 analysis reads observations and does not import the core."""

from datetime import datetime, timedelta
from pathlib import Path

from dealos.analysis.bpi17.analyze import analyze_events
from dealos.analysis.bpi17.birth import collect_births, summarize_births
from dealos.analysis.bpi17.macro_experiments import analyze_macro
from dealos.analysis.bpi17.micro_experiments import context_rows, lifecycle_rows, resource_rows
from dealos.analysis.bpi17.read import Event


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "src" / "dealos" / "analysis"
FORBIDDEN = ("dealos.sim", "dealos.policies", "dealos.generator", "dealos.domain", "dealos.org")


def test_analysis_package_does_not_import_the_core() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in ANALYSIS.rglob("*.py"))
    for name in FORBIDDEN:
        assert name not in text


def test_lifecycle_rows_are_one_occurrence_and_a_later_schedule_is_a_repeat() -> None:
    start = datetime(2016, 1, 1, 9, 0)
    events = [
        _event("c1", 1, start, "W_Call", "Workflow", "User_1", "schedule"),
        _event("c1", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_1", "start"),
        _event("c1", 3, start + timedelta(minutes=2), "W_Call", "Workflow", "User_1", "complete"),
        _event("c1", 4, start + timedelta(hours=5), "W_Validate", "Workflow", "User_2", "schedule"),
        _event("c1", 5, start + timedelta(hours=5, minutes=1), "W_Validate", "Workflow", "User_2", "start"),
        _event("c1", 6, start + timedelta(hours=30), "W_Call", "Workflow", "User_3", "schedule"),
        _event("c1", 7, start + timedelta(hours=30, minutes=2), "A_Concept", "Application", "User_3", "complete"),
        _event("c1", 8, start + timedelta(hours=30, minutes=3), "A_Concept", "Application", "User_4", "complete"),
        _event("c1", 9, start + timedelta(hours=31), "O_Created", "Offer", "User_4", "complete", offer_id="Offer_1"),
        _event("c1", 10, start + timedelta(hours=32), "O_Created", "Offer", "User_4", "complete", offer_id="Offer_2", accepted="true"),
    ]
    result = analyze_events(events)
    case = result["cases"][0]
    assert case["reexecutions"] == 3
    assert case["separated_reexecutions"] == 1
    assert case["adjacent_reexecutions"] == 2
    assert case["resource_changes"] == 3
    assert case["same_activity_resource_changes"] == 1
    assert case["gaps_gt_1h"] >= 1
    assert case["gaps_gt_24h"] == 1
    assert case["gaps_gt_4h"] >= case["gaps_gt_24h"]
    assert case["offers"] == 2
    assert case["open_overlap"] == 0
    call = next(row for row in result["activities"] if row["activity"] == "W_Call")
    assert call["repeat_cases"] == 1
    assert call["different_resource_reexecutions"] == 1
    assert result["durations_seconds"]["count"] == 1
    assert result["summary"]["cases_with_return"] == 1
    mismatch = {row["id"]: row for row in result["mismatches"]}
    assert mismatch["M8"]["extension_candidate"] is False
    assert mismatch["M3"]["extension_candidate"] is False


def test_open_overlap_and_start_to_complete_duration() -> None:
    start = datetime(2016, 2, 1, 8, 0)
    events = [
        _event("c2", 1, start, "W_A", "Workflow", "User_1", "start"),
        _event("c2", 2, start + timedelta(minutes=10), "W_B", "Workflow", "User_1", "start"),
        _event("c2", 3, start + timedelta(minutes=20), "W_A", "Workflow", "User_1", "complete"),
    ]
    result = analyze_events(events)
    assert result["cases"][0]["open_overlap"] == 1
    assert result["durations_seconds"]["count"] == 1
    assert result["durations_seconds"]["median"] == 20 * 60


def test_birth_records_only_the_preceding_event() -> None:
    start = datetime(2016, 3, 1, 9, 0)
    events = [
        _event("c", 1, start, "W_Call", "Workflow", "User_1", "schedule"),
        _event("c", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_1", "complete"),
        _event("c", 3, start + timedelta(hours=2), "W_Validate", "Workflow", "User_2", "complete"),
        _event("c", 4, start + timedelta(hours=3), "W_Call", "Workflow", "User_9", "schedule"),
        _event("c", 5, start + timedelta(hours=4), "A_Concept", "Application", "User_3", "complete"),
        _event("c", 6, start + timedelta(hours=5), "A_Concept", "Application", "User_3", "complete"),
    ]
    births = collect_births(events)
    assert len(births) == 2
    call = next(row for row in births if row["activity"] == "W_Call")
    concept = next(row for row in births if row["activity"] == "A_Concept")
    assert call["predecessor_activity"] == "W_Validate"
    assert call["predecessor_lifecycle"] == "complete"
    assert call["same_resource"] is False
    assert concept["predecessor_activity"] == "A_Concept"
    assert concept["same_resource"] is True
    summary = summarize_births(births)
    assert summary["births"] == 2
    assert summary["activities_with_a_dominant_pair"] == 0


def test_context_window_stops_at_the_case_boundary() -> None:
    start = datetime(2016, 4, 1, 8, 0)
    events = [
        _event("a", 1, start, "W_Other", "Workflow", "User_1", "complete"),
        _event("b", 1, start, "W_Call", "Workflow", "User_1", "schedule"),
        _event("b", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_1", "complete"),
        _event("b", 3, start + timedelta(minutes=2), "W_Call", "Workflow", "", "schedule"),
    ]
    rows = context_rows(events)
    birth_rows = [row for row in rows if row["case_id"] == "b" and row["window"] == 5]
    assert birth_rows
    assert all(row["case_id"] == "b" for row in birth_rows)
    assert max(row["relative_position"] for row in birth_rows) == 2
    assert {row["predecessor_activity"] for row in birth_rows} == {"W_Call"}
    missing = resource_rows(events)
    assert any(row["relation"] == "missing" for row in missing)


def test_macro_counts_stay_inside_the_case_and_the_birth_rule() -> None:
    start = datetime(2016, 6, 1, 8, 0)
    events = [
        _event("a", 1, start, "W_Call", "Workflow", "User_1", "schedule"),
        _event("a", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_1", "start"),
        _event("a", 3, start + timedelta(minutes=2), "W_Call", "Workflow", "User_1", "complete"),
        _event("a", 4, start + timedelta(hours=2), "W_Validate", "Workflow", "User_2", "schedule"),
        _event("b", 1, start, "W_Call", "Workflow", "User_9", "schedule"),
        _event("b", 2, start + timedelta(minutes=5), "A_Concept", "Application", "", "complete"),
    ]
    result = analyze_macro(events)
    user_1 = next(row for row in result["resources"] if row["resource"] == "User_1")
    assert user_1["activities"] == 1
    assert user_1["workflow_activities"] == 1
    pairs = {(row["from_resource"], row["to_resource"]) for row in result["transitions"]["pairs"]}
    assert ("User_1", "User_9") not in pairs
    assert ("User_1", "User_2") in pairs
    assert result["transitions"]["missing_id_pairs"] == 1
    user_2 = next(row for row in result["lifecycle"] if row["resource"] == "User_2")
    assert user_2["birth_events"] == 0
    assert user_2["schedule"] == 1


def test_lifecycle_groups_one_occurrence_and_counts_the_next() -> None:
    start = datetime(2016, 5, 1, 8, 0)
    events = [
        _event("c", 1, start, "W_Call", "Workflow", "User_1", "schedule"),
        _event("c", 2, start + timedelta(minutes=1), "W_Call", "Workflow", "User_1", "start"),
        _event("c", 3, start + timedelta(minutes=2), "W_Call", "Workflow", "User_1", "suspend"),
        _event("c", 4, start + timedelta(minutes=3), "W_Call", "Workflow", "User_1", "complete"),
        _event("c", 5, start + timedelta(minutes=4), "W_Call", "Workflow", "User_2", "schedule"),
        _event("c", 6, start + timedelta(minutes=5), "W_Call", "Workflow", "User_2", "ate_abort"),
    ]
    records = lifecycle_rows(events)
    assert [row["occurrence_number"] for row in records] == [1, 2]
    first, second = records
    assert first["lifecycle_events"] == 4
    assert first["completed"] is True
    assert first["suspended"] is True
    assert second["aborted"] is True
    assert second["completed"] is False
    assert first["duration_seconds"] == 120


def _event(case_id, index, ts, activity, origin, resource, lifecycle, offer_id="", accepted=""):
    return Event(
        case_id=case_id,
        event_index=index,
        ts=ts,
        activity=activity,
        action="",
        origin=origin,
        resource=resource,
        lifecycle=lifecycle,
        offer_id=offer_id,
        accepted=accepted,
        selected="",
        offered_amount="",
    )
