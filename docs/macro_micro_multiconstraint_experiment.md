# Macro-Micro multi-constraint experiment

## 1. Research question

For a fixed Micro task, can DealOS represent several organizational constraints at once, update that organizational state by an explicit event, recompute eligibility from the state after the event, and run the existing Micro update only when every configured constraint holds?

The Micro task is deal_A:A1. Its readiness comes from the existing AND-min rule. Its progress update stays x(t+1) = min(1, x + Δx). The Macro diagnosis is a gate in front of that update.

## 2. Initial state O0

Micro readiness is 1.0, progress is 0.0, and deal_A:A1 is in blocked_tasks: False. Pool `pool` available is 0.0 of total 1.0. `profile` available is False. `external_profile` available is False. Authority grants on `approve_deal`: 0.

## 3. Task constraints

One TaskConstraint on deal_A:A1 names four requirements. Nothing is inferred from event order, activity names, co-occurrence, timestamps, or participation.

- Capacity pool `pool`, required available amount 1.
- Information object `profile`.
- Decision `approve_deal`. Eligibility is an AuthorityGrant or an active delegation. Approve does not create a grant.
- ExternalRelation `buyer_profile`, kind `configured`, context `deal_A`, linked information `external_profile`.

`profile` and `external_profile` are different information objects, so producing one does not receive the other.

## 4. Initial diagnosis

Task `deal_A:A1`. Micro readiness is 1.0. Macro eligible is False. First reason, kept for the existing single-reason field, is `capacity_unavailable`. Blocking reasons: capacity_unavailable;external_information_unavailable;information_unavailable;authority_unavailable. Evidence: capacity_unavailable [pool_id=pool, available=0.0, required=1]; external_information_unavailable [external_relation_id=buyer_profile, information_id=external_profile, available=False, external_kind=configured, external_context=deal_A]; information_unavailable [information_id=profile, available=False]; authority_unavailable [decision_id=approve_deal, authority_holders=]. Progress after the gate is 0.0.

| State | Event | Capacity | Information | Authority | External | Veto | Diagnosis | Eligible | Progress |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| O0 | initial | blocked | blocked | blocked | blocked | resolved | 4 blockers | False | 0.0 |
| O1 | Release | resolved | blocked | blocked | blocked | resolved | 3 blockers | False | 0.0 |
| O2 | ProduceInformation | resolved | resolved | blocked | blocked | resolved | 2 blockers | False | 0.0 |
| O3 | ReceiveExternalInformation | resolved | resolved | blocked | resolved | resolved | 1 blocker | False | 0.0 |
| O4 | AuthorityGrant | resolved | resolved | resolved | resolved | resolved | none | True | 1.0 |

## 5. Event 1 and O1

O0 -- Release --> O1. Removed: capacity_unavailable. Still blocking: authority_unavailable, external_information_unavailable, information_unavailable. Eligible: False. Progress: 0.0.

## 6. Diagnosis after Event 1

Task `deal_A:A1`. Micro readiness is 1.0. Macro eligible is False. First reason, kept for the existing single-reason field, is `external_information_unavailable`. Blocking reasons: external_information_unavailable;information_unavailable;authority_unavailable. Evidence: external_information_unavailable [external_relation_id=buyer_profile, information_id=external_profile, available=False, external_kind=configured, external_context=deal_A]; information_unavailable [information_id=profile, available=False]; authority_unavailable [decision_id=approve_deal, authority_holders=]. Progress after the gate is 0.0.

## 7. Event 2 and O2

O1 -- ProduceInformation --> O2. Removed: information_unavailable. Still blocking: authority_unavailable, external_information_unavailable. Eligible: False. Progress: 0.0.

## 8. Diagnosis after Event 2

Task `deal_A:A1`. Micro readiness is 1.0. Macro eligible is False. First reason, kept for the existing single-reason field, is `external_information_unavailable`. Blocking reasons: external_information_unavailable;authority_unavailable. Evidence: external_information_unavailable [external_relation_id=buyer_profile, information_id=external_profile, available=False, external_kind=configured, external_context=deal_A]; authority_unavailable [decision_id=approve_deal, authority_holders=]. Progress after the gate is 0.0.

## 9. Event 3 and O3

O2 -- ReceiveExternalInformation --> O3. Removed: external_information_unavailable. Still blocking: authority_unavailable. Eligible: False. Progress: 0.0.

## 10. Diagnosis after Event 3

Task `deal_A:A1`. Micro readiness is 1.0. Macro eligible is False. First reason, kept for the existing single-reason field, is `authority_unavailable`. Blocking reasons: authority_unavailable. Evidence: authority_unavailable [decision_id=approve_deal, authority_holders=]. Progress after the gate is 0.0.

## 11. Event 4 and O4

O3 -- AuthorityGrant --> O4. Removed: authority_unavailable. Still blocking: none. Eligible: True. Progress: 1.0.

There is no grant event. O4 places the existing AuthorityGrant record on the decision.

## 12. Final Micro outcome

O4 reason is `can_progress`. Eligible is True. Progress moves from 0.0 to 1.0 by one existing allocation step. Micro readiness at the start of that step is 1.0.

## 13. Alternative event ordering

Sequence B places the grant first, then releases capacity, produces information, and receives the external object. The final eligibility matches sequence A. The intermediate diagnoses follow whichever constraints are still open.

| State | Event | Capacity | Information | Authority | External | Veto | Diagnosis | Eligible | Progress |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | initial | blocked | blocked | blocked | blocked | resolved | 4 blockers | False | 0.0 |
| B1 | AuthorityGrant | blocked | blocked | resolved | blocked | resolved | 3 blockers | False | 0.0 |
| B2 | Release | resolved | blocked | resolved | blocked | resolved | 2 blockers | False | 0.0 |
| B3 | ProduceInformation | resolved | resolved | resolved | blocked | resolved | 1 blocker | False | 0.0 |
| B4 | ReceiveExternalInformation | resolved | resolved | resolved | resolved | resolved | none | True | 1.0 |

## 14. Invariants

Invariant failures: 0.
Seed-0 FIFO fingerprint, 2 completed deals in 40 steps: True.
deal_A:A1 is in blocked_tasks in any recorded state: False.
Micro readiness stays 1 and progress stays 0 until a state has no blocking reasons. SalesEnvironment.step runs only in that state.
Release changes pool availability. ProduceInformation changes the named internal object. ReceiveExternalInformation changes the object named by the external relation. AuthorityGrant adds one grant. None of those writes clears a different constraint.
IssueVeto adds an active veto. The operating model has no retract event, so the recorded removal writes the existing Veto.active field to false. A remaining capacity failure stays after that write. Approve and Participate do not add an AuthorityGrant.

## 15. What the experiment demonstrates

For a fixed Micro task, this run represents four simultaneous organizational constraints, updates organizational state through explicit events, recomputes the task's organizational eligibility after each state transition, and allows the existing Micro update only when the configured constraints are satisfied.

## 16. What it does not demonstrate

It does not show that this constraint set was recovered from a real organization or a real deal log. It does not change Micro readiness, the progress formula, the meaning of blocked_tasks, policies, BPI17 analysis, or the problem-evolution engine. A predecessor-blocked task and an organizationally ineligible task remain different facts.
