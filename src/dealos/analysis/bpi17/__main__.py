"""Run the BPI17 observation analysis and write the report."""

from pathlib import Path

from dealos.analysis.bpi17.analyze import analyze_events
from dealos.analysis.bpi17.export import write_outputs
from dealos.analysis.bpi17.read import load_events


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    events = load_events(root / "data" / "bpi17" / "events_normalized.csv")
    write_outputs(analyze_events(events), root)


if __name__ == "__main__":
    main()
