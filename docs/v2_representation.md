# V2 occurrence decisions

TaskType is not TaskOccurrence. A task type is a vertex of the deal DAG. A task occurrence is one execution of that type. Readiness is not lifecycle, and neither is allocation eligibility.

## What changed, and why

BPI17 showed three representation gaps. 1,723 of 3,000 cases open another occurrence of an activity that already occurred. Workflow events use schedule, start, suspend, resume, complete, abort, and withdraw, which is not a single progress value. Every case has application, offer, and workflow events, and 860 cases have more than one OfferID.

The type-level AND-DAG is unchanged. Allocations now name `(deal_id, occurrence_id, resource_id)`. Random, FIFO, and Bottleneck choose among eligible occurrences. Bottleneck's score is still the number of incomplete downstream task types. With one occurrence per type, that list is the same sequence as the old eligible-task list, so the synthetic presets keep their previous trajectories.

Lifecycle, readiness, and eligibility are separate:

- Lifecycle is whether this execution is scheduled, active, suspended, completed, aborted, or withdrawn.
- Readiness for the primary occurrence is still AND-min of predecessor type progress. An added occurrence starts unresolved. A fixture may call `declare_ready`, which uses Ready = 1 because no predecessor occurrence is known. That declaration is synthetic.
- Eligibility is active lifecycle and a satisfied readiness value. A suspended occurrence can sit on a type that is ready and still receive no progress. An active occurrence can be blocked by type readiness, or unresolved, and then it is not eligible.

`completed_deals` remains the count of deals whose primary target progress is complete. It is not a BPI17 success label. Rollouts also record how many occurrences are active, completed, suspended, aborted, or withdrawn.

## What V2 can represent

- More than one execution of the same task type, addressed by different actions, sharing capacity, with independent progress.
- A completed occurrence that stays complete while another occurrence of that type is still open.
- Suspend, abort, and withdraw without treating them as successful completion.
- An offer id stored on the case, without attaching it to a workflow occurrence.

## What V2 still cannot represent

- Which predecessor occurrence gates which successor. BPI17 does not currently provide enough evidence to infer occurrence-level causal dependencies.
- A long timestamp gap as internal work, external waiting, or missing records.
- A resource-identifier change as a handoff, a role, or an authority grant.
- Accept, deny, and cancel activities as authority.
- An information link between systems.
- An offer as the parent of a workflow.
- `x` in `[0, 1]` as a measured BPI17 quantity. The float remains the synthetic progress variable.

## Mismatch classification

This classification is about the representation, not a new fit of the log. The event counts are the ones already computed in `analysis/bpi17_pattern_catalog.json`.

| Id | Status | Why |
| --- | --- | --- |
| M1 recurrence | RESOLVED at the representation level | A second occurrence can be created explicitly and allocated on its own. The log still does not say why it was created. |
| M2 object identity | RESOLVED at offer identity | `Offer` stores a non-empty OfferID on a case. There is no case-offer-workflow tree. |
| M5 lifecycle | PARTIALLY RESOLVED | Lifecycle is stored separately from progress and from eligibility. The log's fraction of work, if any, is still not `x`. |
| M6 return | UNRESOLVED | A return in the activity sequence is not an edge between occurrences. No such edge is inferred. |
| M3 long gaps | UNRESOLVED | A gap is not given a cause. |
| M4 resource changes | UNRESOLVED | A different resource id is not a handoff. |
| M7 authority | UNRESOLVED | Activity names are not authority grants. |
| M8 information links | UNRESOLVED | The log has no such field, and the model does not add one. |

## Synthetic assumptions

- The primary occurrence of each task type starts `active` when progress is below 1, so the existing one-occurrence step still adds progress.
- `declare_ready` sets Ready = 1 for that occurrence only. It is a test switch, not a reading of BPI17.
- Deal completion is still primary target progress. It is not accepted versus denied versus cancelled.
