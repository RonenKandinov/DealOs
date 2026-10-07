# Representation-gap experiment

## Question

When deal_A:A1 is Micro-ready and every configured TaskConstraint holds, the current diagnosis is can_progress. If a recorded outcome still says the task did not progress, which kind of gap is that?

The classifier has three gap labels. `no_gap` means none of the three applies.

- `observation_gap`: a field required to compare the prediction with the outcome was not supplied.
- `representation_gap`: those fields were supplied, and the current TaskConstraint has no remaining failure that can express an explanation.
- `semantic_gap`: a proposal explains the outcome by a semantic assumption the operating model does not support.

## Fixed Micro task and satisfied Macro state

Task `deal_A:A1`. Micro readiness 1.0. Progress before any allocation 0.0. In blocked_tasks: False.
Diagnosis reason `can_progress`. Blocking reasons: 0.
Capacity is available, `profile` is available, `external_profile` is available, an AuthorityGrant is present, and no veto is active. Those are the fields TaskConstraint can name.

## Results

| scenario | observations_available | current_model_prediction | observed_outcome | classification | candidate | accepted |
| --- | --- | --- | --- | --- | --- | --- |
| hidden_causal_observation | False | can_progress | hidden | observation_gap | none | False |
| unexplained_non_progress | True | can_progress | 0.0 | representation_gap | UnmodeledConstraint | True |
| unsupported_causal_story | True | can_progress | 0.0 | semantic_gap | TimeGapIsWaiting | False |
| explained_progress | True | can_progress | 1.0 | no_gap | none | False |

## Scenarios

Hidden causal observation. The constraint flags are filled and `observed_progress` is withheld. The label is observation_gap. The same prediction is not called a representation gap while the outcome is missing.

Complete current observations. `observed_progress` is the supplied value 0. The diagnosis remains can_progress because no configured constraint fails. The label is representation_gap. No cause is assigned to that 0.

The candidate on that row is UnmodeledConstraint: a named slot with an empty assumption list. The validator accepts that slot because it does not state a cause. Acceptance here means the proposal was not rejected for unsupported semantics. The slot is not installed, and acceptance is not evidence that the slot is the true cause.

Unsupported causal story. The same complete record is paired with a proposal whose assumption is `time_gap_is_waiting`. A time gap is not waiting in the operating model. The label is semantic_gap and the candidate is rejected.

Explained progress. The gate is can_progress, so the existing allocation step runs. The recorded progress is that step's result. The prediction matches it. The label is no_gap.

## Checks that stayed in place

Macro-Micro integration rows and invariants still pass: True.
Seed-0 FIFO fingerprint, 2 completed deals in 40 steps: True.

## What the experiment demonstrates

A missing outcome, a complete outcome the current constraint fields cannot explain, and a proposal that adds an unsupported meaning receive three different labels. A matching outcome receives no gap label.

## What it does not demonstrate

It does not identify why the supplied progress was 0. It does not show that UnmodeledConstraint is a real organizational fact. It does not install that slot, and it does not change Micro readiness, the progress formula, policies, BPI17 analysis, or the existing organizational primitives.
