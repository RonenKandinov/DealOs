"""Seeded synthetic enterprise-sales portfolios."""

from dealos.generator.generate import generate_scenario
from dealos.generator.presets import PRESETS, get_preset

__all__ = ["PRESETS", "generate_scenario", "get_preset"]
