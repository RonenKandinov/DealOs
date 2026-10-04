"""Fixed BPI17 mismatch records for the one-cycle demo.

Statuses stay FACT, INFERENCE, or HYPOTHESIS. A hypothesis is not promoted here.
"""

from __future__ import annotations

from dealos.problem_evolution.models import Mismatch


def bpi17_mismatches() -> tuple[Mismatch, ...]:
    return (
        Mismatch(
            "M1",
            "recurrence",
            "FACT",
            "1,723/3,000 cases open another occurrence of an activity",
            "A task type is one execution.",
            "The log shows another occurrence. It does not say the earlier work was undone.",
            prevalence="1723/3000",
        ),
        Mismatch(
            "M2",
            "object_identity",
            "INFERENCE",
            "OfferID on offer events; 860/3,000 cases have more than one OfferID",
            "The deal graph has no offer identity.",
            "OfferID identifies an offer. It does not make the offer the parent of the workflow.",
            prevalence="860/3000",
        ),
        Mismatch(
            "M5",
            "lifecycle",
            "FACT",
            "Workflow events use schedule, start, suspend, resume, complete, abort, and withdraw",
            "Progress x is the only execution state.",
            "Those event names are a lifecycle. x in [0, 1] is not a measured BPI17 quantity.",
            prevalence="suspend in 2989/3000",
        ),
        Mismatch(
            "M4",
            "resource_change",
            "HYPOTHESIS",
            "Resource identifiers change between consecutive events",
            "A changed resource id has no handoff reading.",
            "The identifier changed. The log does not say responsibility was transferred.",
            candidate_required=False,
            prevalence="2992/3000",
        ),
    )
