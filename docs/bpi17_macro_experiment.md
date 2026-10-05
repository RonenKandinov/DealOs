# BPI17 macro experiment

This file is the whole experiment: the decision, the activity profiles, the resource-id transitions, and the lifecycle counts. The csv files hold the full tables.

## BPI17 macro experiment summary

The table has 3000 cases and 113903 events. org:resource is the identifier on the event. No semantic field for person, role, department, owner, or authority is present, so none was substituted.

### 1. What org:resource lets us observe

FACT: an identifier, the activity name, the lifecycle name, the case, and the timestamp.
The field does not say who the identifier is.

### 2. Activity profiles

FACT: median distinct activities 14. Median share in the top activity 0.33. Resources with top share at least 80%: 0.
FACT: resources in at least 30 cases account for 97.5% of events. Among those resources, 67.9% have a stable top-activity share under the 0.10 rule.
INFERENCE: the typical identifier is spread across many activity names.
HYPOTHESIS: the identifier is a generalist employee.

### 3. Transitions

FACT: 5873 directed pairs. The top 1% cover 11.3% of id changes. Concentrated: False. Reverse direction also observed for 3382 directed pairs.
INFERENCE: a low top-1% share means the changes are diffuse.
HYPOTHESIS: a directed pair is an organizational handoff.

### 4. Lifecycle

FACT: 0 resources meet the lifecycle concentration rule. Complete events are common because application and offer rows are recorded as complete.
HYPOTHESIS: presence on a complete row is authority to complete.

### 5. Cross-case persistence

FACT: 109 identifiers appear in at least 30 cases. Median activities per identifier: 14. Identifiers at or above that median: 79.
INFERENCE: many identifiers recur across cases and activities, so they behave like persistent ids in this extract.
HYPOTHESIS: the identifier is a person who owns the work.

### 6. A macro-level entity

Only if the persistence bar is met: resources in at least 30 cases carry at least half of events, and at least half of those resources keep a stable top-activity share. Otherwise the ids are persistent strings with unstable activity mixes, which is not enough to add an entity.

### 7. A macro-level relationship

Only if the top 1% of directed id pairs cover at least half of id changes. Otherwise the transitions do not form a small observed network.

### 8. Facts

The counts in the three reports: activity breadth, top shares, entropy, directed-pair concentration, lifecycle shares, and gap buckets.

### 9. Inferences

A broad activity list means the id is seen on many activity names. A diffuse pair list means changes are spread out. A stable top share means the same activity name remains common inside each case.

### 10. Hypotheses

Person, role, department, authority, ownership, handoff, and waiting. None of these fields exist in the log.

### 11. A new macro primitive

Candidates that met a predeclared bar: persistent resource identifier.
A candidate is a name for a later representation discussion. It is not implemented in this pass.

### 12. If a candidate is named

persistent resource identifier: the id recurs across cases and its top activity share stays within 0.10 of the global share. It would let a later model point at the same id across events. It would not prove a person or a role.
observed resource-id transition: a small set of directed pairs would cover at least half of id changes. It would let a later model store those observed pairs. It would not prove a handoff.

### 13. If no candidate is named

The ids are real and the transitions are real, and both are already describable as fields on events. Unstable mixes and a long pair list do not force a new object.

### Decision

MACRO CANDIDATE IDENTIFIED

Named candidates, not implemented: persistent resource identifier.

## BPI17 resource activity profiles

org:resource is an observed identifier. A broad activity list is not a role, a department, or a person.

FACT: 143 resource ids. Median distinct activities 14. Median share in the most common activity 0.33. Median entropy 2.89 bits.
FACT: 0 resources have at least 80% of their events in one activity.
FACT: among resources in at least 10 cases, a profile is called stable when the median per-case share of the global top activity is within 0.10 of the global share. Stable share of resources that appear in at least 30 cases: 67.9%.

INFERENCE: identifiers that touch many activities participate across more than one observed activity name.
HYPOTHESIS: such an identifier is a generalist employee. The log does not say that.

| Resource | Events | Activities | Top activity | Top share | Entropy | Cases | Stable |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| User_1 | 13949 | 11 | W_Handle leads | 25.3% | 2.93 | 2245 | True |
| User_3 | 2463 | 19 | W_Call after offers | 33.6% | 3.00 | 573 | True |
| User_5 | 2307 | 19 | W_Call after offers | 33.6% | 3.13 | 546 | True |
| User_87 | 2100 | 22 | W_Validate application | 61.5% | 2.03 | 422 | False |
| User_30 | 2092 | 21 | W_Validate application | 50.3% | 2.12 | 370 | True |
| User_29 | 2006 | 21 | W_Validate application | 35.3% | 2.55 | 307 | True |
| User_123 | 1957 | 9 | W_Validate application | 47.3% | 2.23 | 298 | True |
| User_100 | 1920 | 21 | W_Validate application | 37.4% | 2.27 | 350 | True |
| User_2 | 1909 | 21 | W_Call incomplete files | 35.4% | 3.07 | 456 | True |
| User_49 | 1896 | 16 | W_Complete application | 26.7% | 3.08 | 385 | True |
| User_28 | 1874 | 18 | W_Call after offers | 20.4% | 3.31 | 362 | False |
| User_68 | 1799 | 20 | W_Validate application | 46.9% | 2.40 | 260 | True |
| User_121 | 1770 | 9 | W_Validate application | 46.8% | 2.27 | 290 | True |
| User_27 | 1680 | 19 | W_Validate application | 32.9% | 3.15 | 278 | False |
| User_116 | 1651 | 9 | W_Validate application | 51.4% | 2.12 | 279 | True |

The table shows the 15 identifiers with the most events. The csv has every identifier.

## BPI17 resource-id transitions

A directed pair is two different resource ids on consecutive events in the same case. The pair is an observed transition. It is not a handoff and not an organizational graph.

FACT: 20444 consecutive pairs change the resource id, across 5873 directed pairs. The most frequent 1% of those pairs (59 pairs) cover 11.3% of the changes. Concentrated, under the half-share rule: False.
FACT: 3382 directed pairs also appear in the reverse direction.
FACT: consecutive pairs with a missing resource id: 0. Negative gaps among id changes: 0.

- same activity, different id: 14528
- different activity, different id: 5916
- same id, different activity: 62850
- same id, same activity: 27609

Gap buckets count only pairs whose resource id changes. A bucket is not a wait.

| Bucket | Same activity | Different activity |
| --- | ---: | ---: |
| 0_1h | 2332 | 728 |
| 1_4h | 2355 | 715 |
| 4_8h | 1043 | 344 |
| 8_24h | 1768 | 991 |
| 24_72h | 2280 | 1416 |
| gt_72h | 4750 | 1722 |

INFERENCE: if the top 1% cover is low, id changes are spread across many pairs.
HYPOTHESIS: a frequent pair is a standing organizational link. That is not established.

## BPI17 resource identifiers and lifecycle names

A resource id on a complete event is only present on that event. It is not authority to complete. Application and offer events in this log are recorded as complete, so a high complete share can come from those origins.

FACT: 0 resources have at least 100 events and at least 80% of them in one lifecycle name.

| Resource | Events | Top lifecycle | Share | Birth events | Concentrated |
| --- | ---: | --- | ---: | ---: | --- |
| User_1 | 13949 | complete | 51.6% | 569 | False |
| User_3 | 2463 | complete | 34.9% | 155 | False |
| User_5 | 2307 | complete | 35.9% | 181 | False |
| User_87 | 2100 | suspend | 28.9% | 93 | False |
| User_30 | 2092 | complete | 30.8% | 148 | False |
| User_29 | 2006 | complete | 40.2% | 238 | False |
| User_123 | 1957 | complete | 32.3% | 230 | False |
| User_100 | 1920 | complete | 26.8% | 162 | False |
| User_2 | 1909 | suspend | 29.4% | 131 | False |
| User_49 | 1896 | complete | 41.6% | 102 | False |
| User_28 | 1874 | complete | 42.2% | 160 | False |
| User_68 | 1799 | complete | 37.1% | 134 | False |
| User_121 | 1770 | complete | 32.5% | 204 | False |
| User_27 | 1680 | complete | 36.7% | 164 | False |
| User_116 | 1651 | complete | 30.2% | 253 | False |

INFERENCE: a concentrated lifecycle share means that name dominates the identifier's events.
HYPOTHESIS: the identifier is responsible for that lifecycle stage. The log does not say that.
