# BPI17 micro experiment summary

The three checks use the existing 3,000-case table. The required fields are case id, event index, timestamp, activity, lifecycle, and resource. None of those fields is missing, so no count was filled in.

## 1. Birth context

FACT: the event immediately before the birth is the same at k = 1, k = 3, and k = 5. Its share does not move when the window grows.
FACT: O_Created / complete is the immediate predecessor of 58.0% of O_Sent (mail and online) births, and it appears somewhere in the window for 97.0% at k = 3 and 99.2% at k = 5. The other named pairs stay near their k = 1 share inside the longer window.
UNRESOLVED: any of those pairs causes the birth.

## 2. Resource continuity

FACT: 92.9% of 9145 births carry the same resource id as the preceding event. 7.1% differ. Missing ids: 0.
INFERENCE: the same identifier is often present on both sides of the birth.
HYPOTHESIS: that identifier is ownership or a handoff. Neither is established.

## 3. Lifecycle of repeated occurrences

FACT: 46543 first occurrences and 9145 additional occurrences were grouped without splitting one workflow occurrence into repeats.
FACT: a complete event is present on 82.6% of first occurrences and 78.7% of additional occurrences.
FACT: an ate_abort event is present on 13.6% of first occurrences and 17.8% of additional occurrences.
HYPOTHESIS: abort means failure, suspend means waiting, or a repeat means rework.

## 4. Strong facts

- The immediate predecessor is stable for 9 of 11 frequent birth activities under the half-share rule, and those immediate shares do not move when the window grows.
- Same resource id: 92.9% of births. Different resource id: 7.1%.
- First and additional occurrences can be counted separately, and their lifecycle mixes are not the same.

## 5. Inferences

- A high same-id share is consistent with the identifier continuing across the two events.
- A lower complete share on additional occurrences is consistent with those occurrences more often ending without a complete event.

## 6. Hypotheses that stay open

- The predecessor causes the birth.
- A resource change is a handoff, a role change, or an authority transfer.
- The same resource id means ownership.
- Suspend is waiting, abort is failure, and a repeat is rework.
- A return to an activity is an occurrence-level dependency.

## 7. A new representation primitive

No. The three checks describe births, identifiers, and lifecycle names the current representation can already store as occurrences and lifecycle values. They do not force a new primitive.

## 8. Occurrence-level dependencies

No. A pair at 100% in a window is still a frequency. No edge was added.

## 9. Readiness

No. Extra-occurrence readiness stays unresolved.

## 10. The decision layer

No. Policies should keep allocating to the primary occurrence. The birth patterns are not eligibility rules.

## Decision

MICRO SHOULD REMAIN FROZEN

The evidence is strong as description. It is not sufficient to add a dependency, a readiness rule, or a change to allocation. The predecessor of a birth, the resource id, and the lifecycle mix can sit in a report. They do not yet say what the simulator should do differently.
