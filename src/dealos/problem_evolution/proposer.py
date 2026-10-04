"""Replaceable proposer. The MVP implementation is a fixed rule table."""

from __future__ import annotations

from typing import Protocol

from dealos.problem_evolution.models import Mismatch, MutationProposal, Representation
from dealos.problem_evolution.mutations import add_lifecycle, add_object, add_occurrence


class MutationProposer(Protocol):
    def propose(
        self,
        representation: Representation,
        mismatches: tuple[Mismatch, ...],
        history: tuple[object, ...],
    ) -> list[MutationProposal]:
        """Return proposals. Must not rewrite a HYPOTHESIS into a FACT."""


class RuleBasedMutationProposer:
    """Map named evidence rules onto the small operator set.

    M4 does not produce a handoff operator. No such operator is in the grammar.
    """

    def propose(
        self,
        representation: Representation,
        mismatches: tuple[Mismatch, ...],
        history: tuple[object, ...] = (),
    ) -> list[MutationProposal]:
        del representation, history
        proposals: list[MutationProposal] = []
        for mismatch in mismatches:
            if mismatch.status == "HYPOTHESIS":
                continue
            if mismatch.mismatch_id == "M1" and mismatch.category == "recurrence":
                proposals.append(
                    MutationProposal(
                        "AddOccurrence",
                        "execution",
                        (mismatch.mismatch_id,),
                        "FACT: another occurrence of an activity is in the log. "
                        "The proposal adds TaskOccurrence. It does not call that rework.",
                        add_occurrence(),
                    )
                )
            elif mismatch.mismatch_id == "M5" and mismatch.category == "lifecycle":
                proposals.append(
                    MutationProposal(
                        "AddLifecycle",
                        "lifecycle",
                        (mismatch.mismatch_id,),
                        "FACT: workflow events carry a lifecycle. "
                        "The proposal adds that state. It does not claim x was measured.",
                        add_lifecycle(),
                    )
                )
            elif mismatch.mismatch_id == "M2" and mismatch.category == "object_identity":
                proposals.append(
                    MutationProposal(
                        "AddObject",
                        "object_identity",
                        (mismatch.mismatch_id,),
                        "INFERENCE: OfferID names an offer object. "
                        "The proposal adds OfferIdentity. It does not link offers to workflow tasks.",
                        add_object(),
                    )
                )
        return proposals
