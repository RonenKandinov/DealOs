"""The BPI17 analysis reads observations and does not import the core."""

from datetime import datetime, timedelta
from pathlib import Path

from dealos.analysis.bpi17.analyze import analyze_events
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
