# Ground-truth representation gap

## Question

Can the current Macro gate be shown incomplete when a hidden rule in the world decides an outcome the gate predicts incorrectly, and can a candidate fitted on some worlds be scored on others?

## Layers

Ground truth holds the decision, the eligible holders, the prior actor, and a DutyExclusion rule. The projected OrgState copies capacity, information, external information, and one AuthorityGrant per holder. It has no field for the rule. diagnose reads that state and predicts. The observation lists the gate fields, the decision id, the eligible holders, the prior actor, and the generated progress. The hidden fields required_clear and active never appear in it.

## Hidden rule

DutyExclusion(decision_id, prior_actor_id, required_clear, active). Clear holders are eligible holders other than the prior actor. An active rule allows progress only when the clear count reaches required_clear. An inactive or absent rule leaves the gate's answer in place.

The alternatives were weaker. GovernanceBody.quorum is already stored and simply unread by the gate. SLA breach and capability requirements already have entities and events. Information expiry would read a time gap, which this repository does not read as waiting.

## Worlds

| scenario | split | hidden parameters | eligible holders | prior | prediction | outcome | mismatch | classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | proposal | required_clear=1;active=True;prior_actor_id=Alice | Alice | Alice | can_progress | blocked | True | representation_gap |
| G2 | proposal | required_clear=1;active=True;prior_actor_id=Alice | Alice, Bob | Alice | can_progress | progress | False | no_gap |
| G3 | proposal | required_clear=2;active=True;prior_actor_id=Alice | Alice, Bob | Alice | can_progress | blocked | True | representation_gap |
| G4 | holdout | required_clear=2;active=True;prior_actor_id=Alice | Alice, Bob, Carol | Alice | can_progress | progress | False | no_gap |
| G5 | holdout | required_clear=1;active=False;prior_actor_id=Alice | Alice, Bob, Carol | Alice | can_progress | progress | False | no_gap |
| G6 | holdout | none | Alice | Alice | can_progress | progress | False | no_gap |

The hidden parameters column is for the reader. It is written after evaluation and is an input to neither diagnose nor propose.

## Candidates

propose sees only the public rows of G1, G2, G3. Fit bias: the smallest threshold per observed decision id that agrees with every proposal row. Holdout is G4, G5, G6.

| candidate | fitted thresholds | admissible | fitted | proposal | holdout | coverage | contradiction resolution | regression | specificity | semantic safety | complexity | supported |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UnmodeledConstraint | none | True | True | 1/3 | 3/3 | 4/6 | False | True | True | True | 0 | False |
| DutyExclusion | approve_budget=2, approve_deal=1 | True | True | 3/3 | 3/3 | 6/6 | True | True | True | True | 2 | True |
| DecisionQuorum | approve_budget=3, approve_deal=2 | True | True | 3/3 | 3/3 | 6/6 | True | True | True | True | 1 | True |
| TimeGapIsWaiting | none | False | False | 1/3 | 3/3 | 4/6 | False | True | True | False | 1 | False |

supported means admissible, fitted, and correct on every proposal and holdout world. It does not install the candidate and it is not a claim that the rule exists outside these worlds.

## Extra holdout grid

48 generated worlds: decisions approve_deal (required_clear 1), approve_budget (required_clear 2), approve_contract (required_clear 3), clear-holder count 0 to 3, prior actor inside or outside the holder set, rule active or inactive. None of these rows was shown to propose.

| candidate | grid correct | failures by category |
| --- | --- | --- |
| UnmodeledConstraint | 39/48 | unseen_decision 9 |
| DutyExclusion | 39/48 | inactive_rule 4, unseen_decision 5 |
| DecisionQuorum | 35/48 | inactive_rule 6, prior_not_holder 2, unseen_decision 5 |
| TimeGapIsWaiting | 39/48 | unseen_decision 9 |

unseen_decision: the decision id was not in any proposal row, so the candidate falls back to the gate. inactive_rule: the rule is inactive in ground truth and the observation has no field for that. prior_not_holder: the prior actor is outside the holder set, where holder count and clear count differ.

The raw grid count does not rank. DutyExclusion is correct on 4 grid worlds where the placeholder is wrong (active rules that block), and wrong on 4 grid worlds where the placeholder is right (inactive rules with a low clear count).

## Checks that stayed in place

Macro-Micro integration rows and invariants still pass: True.
Seed-0 FIFO fingerprint, 2 completed deals in 40 steps: True.
TaskConstraint and the operating-model entities have no DutyExclusion field.

## What the experiment demonstrates

A rule stored only in the world makes the current gate predict can_progress while the generated outcome is blocked, and the gap classifier labels that a representation gap from the public record alone. A matching world on the same decision is labelled no gap. A candidate fitted on three public rows can be scored on three held-out worlds and on a generated grid, with its failures sorted by cause.

## What it does not demonstrate

It does not show that duty exclusion is a real organizational fact. It does not validate the ontology against enterprise data. It does not show that the search list contains every possible primitive, or that the fitted candidate is correct beyond these worlds. The named worlds do not separate DutyExclusion from DecisionQuorum; only grid rows with the prior actor outside the holder set do. No candidate observes whether a rule is active, so inactive-rule worlds with a low clear count are mispredicted by every threshold candidate.
