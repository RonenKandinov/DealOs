"""Copy a parent representation and append one mutation. The parent is not edited."""

from __future__ import annotations

from dealos.problem_evolution.models import CandidateRepresentation, MutationProposal, Representation


def generate_candidates(
    representation: Representation,
    proposals: list[MutationProposal],
) -> list[CandidateRepresentation]:
    candidates: list[CandidateRepresentation] = []
    for index, proposal in enumerate(proposals, start=1):
        candidate_id = f"R{index}"
        candidates.append(
            CandidateRepresentation(
                parent_representation_id=representation.representation_id,
                candidate_id=candidate_id,
                mutations=(proposal.mutation,),
                representation=representation.with_component(proposal.mutation.adds, candidate_id),
            )
        )
    return candidates
