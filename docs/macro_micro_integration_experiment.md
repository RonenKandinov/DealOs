# Macro-Micro integration experiment

The question is whether the same Micro task, with the same readiness, gets a different outcome when only the Macro state changes.

Each world resets chain_debug_scenario. deal_A:A1 starts at progress 0 and is not predecessor-blocked. diagnose is the gate. SalesEnvironment.step runs only when the reason is can_progress.

## Comparison

| World | Micro state | Macro difference | Eligibility | Reason | Progress |
| --- | --- | --- | --- | --- | --- |
| W1 | ready, progress 0.0 | capacity available | True | can_progress | 1.0 |
| W2 | ready, progress 0.0 | capacity exhausted | False | capacity_unavailable | 0.0 |
| W3 | ready, progress 0.0 | information unavailable | False | information_unavailable | 0.0 |
| W4 | ready, progress 0.0 | authority unavailable | False | authority_unavailable | 0.0 |
| W5 | ready, progress 0.0 | active veto | False | veto | 0.0 |
| W6 | ready, progress 0.0 | external information unavailable | False | external_information_unavailable | 0.0 |

## Diagnosis

W1: task deal_A:A1. reason can_progress. evidence task_id=deal_A:A1, ready=True, pool_id=pool, available=1.0, required=1.
W2: task deal_A:A1. reason capacity_unavailable. evidence task_id=deal_A:A1, ready=True, pool_id=pool, available=0.0, required=1.
W3: task deal_A:A1. reason information_unavailable. evidence task_id=deal_A:A1, ready=True, information_id=profile, available_information=False.
W4: task deal_A:A1. reason authority_unavailable. evidence task_id=deal_A:A1, ready=True, decision_id=approve_deal, authority_holders=, active_vetoes=.
W5: task deal_A:A1. reason veto. evidence task_id=deal_A:A1, ready=True, decision_id=approve_deal, authority_holders=approver, active_vetoes=v1.
W6: task deal_A:A1. reason external_information_unavailable. evidence task_id=deal_A:A1, ready=True, external_relation_id=buyer_profile, external_kind=configured, external_context=deal_A, information_id=profile, available_information=False.

## Results

Rows passed: 18/18.
Invariant failures: 0.
Seed-0 FIFO fingerprint, 2 completed deals in 40 steps: True.
blocked_tasks contains deal_A:A1 in these worlds: False.

This shows that the implemented Macro state can stop or allow the existing Micro update through an explicit TaskConstraint. It does not show that the ontology was recovered from a real deal log.

MACRO MICRO COUPLING DEMONSTRATED
