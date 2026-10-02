"""Command line entry: python -m dealos.experiments --preset balanced --seeds 0 1 2"""

from __future__ import annotations

import argparse

from dealos.experiments.metrics import format_report
from dealos.experiments.runner import run_experiment
from dealos.generator.presets import PRESETS


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the same synthetic sales portfolio under the V1 baseline policies."
    )
    parser.add_argument("--preset", default="balanced", choices=sorted(PRESETS))
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--horizon", type=int, default=None)
    args = parser.parse_args(argv)
    report = run_experiment(args.preset, args.seeds, horizon=args.horizon)
    print(format_report(report))


if __name__ == "__main__":
    main()
