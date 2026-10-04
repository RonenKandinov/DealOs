"""Load the normalized BPI17 table. Precomputed inference columns are ignored."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Event:
    case_id: str
    event_index: int
    ts: datetime
    activity: str
    action: str
    origin: str
    resource: str
    lifecycle: str
    offer_id: str
    accepted: str
    selected: str
    offered_amount: str


def load_events(path: str | Path) -> list[Event]:
    events: list[Event] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            events.append(
                Event(
                    case_id=row["case_id"],
                    event_index=int(row["event_index"]),
                    ts=_parse_ts(row["ts"]),
                    activity=row["activity"],
                    action=row.get("Action", ""),
                    origin=row.get("EventOrigin", ""),
                    resource=row.get("resource", ""),
                    lifecycle=row.get("lifecycle:transition", ""),
                    offer_id=row.get("OfferID", ""),
                    accepted=row.get("Accepted", ""),
                    selected=row.get("Selected", ""),
                    offered_amount=row.get("OfferedAmount", ""),
                )
            )
    events.sort(key=lambda event: (event.case_id, event.event_index))
    return events


def _parse_ts(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text)
