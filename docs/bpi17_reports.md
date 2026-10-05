# DealOS BPI17 reports

This file collects the separate BPI17 and representation reports. The counts are unchanged.


---

# BPI17 validation report

This report compares the BPI Challenge 2017 loan-application sample with the current DealOS micro and macro representations. The counts are recomputed from case, time, activity, resource, lifecycle, and offer fields. The package columns that already name a handoff, a repeat, or a DealOS element are not used.

A pattern is called recurring when it appears in at least half of the cases. That cutoff is a reporting rule. It is not a significance test.

## 1. Dataset profile

FACT: the table contains 113903 events, 3000 cases, 25 activities, and 143 resource identifiers.
FACT: event origins are Application=22716, Workflow=72324, Offer=18863.
FACT: lifecycle transitions are complete=45662, schedule=14109, withdraw=2066, start=12130, suspend=20073, ate_abort=7944, resume=11919.
INFERENCE: names beginning with A_ are application-object events, O_ are offer-object events, and W_ are workflow activities, because that is how the source names them and how EventOrigin is filled.
HYPOTHESIS: none of those names is yet a DealOS task, role, or authority state.

## 2. Case structure

FACT: events per case have median 35.00, 90th percentile 59.00, and maximum 148.
FACT: distinct resource identifiers per case have median 6.00, 90th percentile 11.00, and maximum 24.
FACT: observed case duration in days has median 18.89, 90th percentile 35.40, and maximum 101.76.
FACT: 3000 cases contain both an Application event and an Offer event.
INFERENCE: a case is a candidate deal object. The log does not define target tasks or a completion rule.

## 3. Activity structure

FACT: 6 activities occur in every case. The others are absent from some cases.
INFERENCE: absence from some cases is the kind of fact an optional task can record. The log does not show the AND edges that would make that task the same object as a V1 task.

| Activity | Events | Cases | Repeat cases | Resources |
| --- | ---: | ---: | ---: | ---: |
| W_Validate application | 19836 | 2084 | 1112 | 112 |
| W_Call after offers | 18070 | 2975 | 327 | 132 |
| W_Call incomplete files | 15619 | 1420 | 529 | 121 |
| W_Complete application | 14036 | 3000 | 1 | 114 |
| W_Handle leads | 4501 | 1939 | 1 | 65 |
| O_Create Offer | 4196 | 3000 | 860 | 108 |
| O_Created | 4196 | 3000 | 860 | 108 |
| O_Sent (mail and online) | 3880 | 2940 | 697 | 100 |
| A_Validating | 3657 | 2084 | 1107 | 102 |
| A_Accepted | 3000 | 3000 | 0 | 107 |
| A_Concept | 3000 | 3000 | 0 | 102 |
| A_Create Application | 3000 | 3000 | 0 | 98 |
| A_Complete | 2975 | 2975 | 0 | 105 |
| O_Returned | 2222 | 2076 | 145 | 42 |
| A_Incomplete | 2157 | 1420 | 529 | 57 |
| O_Cancelled | 2067 | 1513 | 400 | 109 |
| A_Submitted | 1939 | 1939 | 0 | 1 |
| A_Pending | 1593 | 1593 | 0 | 38 |
| O_Accepted | 1593 | 1593 | 0 | 38 |
| A_Cancelled | 1002 | 1002 | 0 | 74 |
| O_Refused | 512 | 386 | 93 | 40 |
| A_Denied | 393 | 393 | 0 | 45 |
| W_Assess potential fraud | 249 | 26 | 2 | 20 |
| O_Sent (online only) | 197 | 181 | 11 | 69 |
| W_Shortened completion  | 13 | 4 | 0 | 3 |

## 4. Resource structure

FACT: 143 distinct org:resource values appear.
FACT: the median number of activities per resource is 14. The median share of a resource's events that sit in its single most common activity is 0.33.
FACT: 0 resources have at least 80 percent of their events in one activity. 136 resources appear in five or more activities.
FACT: the activities touched by the most resources are W_Call after offers (132), W_Call incomplete files (121), W_Complete application (114), W_Validate application (112), O_Cancelled (109).
INFERENCE: org:resource is an observed identifier. It is a candidate for an actor id.
HYPOTHESIS: specialization is not a role, a department, or an authority grant. No source field names a manager, a counsel, or an executive.

## 5. Temporal structure

FACT: gap counts are nested. A gap above 72 hours is also a gap above 1 hour.
FACT: 18309 consecutive pairs are >1 hour, in 2989 cases (99.6%). In 17384 of those pairs the resource identifier also changes (94.9% of the pairs). In 12904 of those pairs both events have the same activity name (70.5%).
FACT: 14788 consecutive pairs are >4 hours, in 2983 cases (99.4%). In 14314 of those pairs the resource identifier also changes (96.8% of the pairs). In 10167 of those pairs both events have the same activity name (68.8%).
FACT: 13321 consecutive pairs are >8 hours, in 2978 cases (99.3%). In 12927 of those pairs the resource identifier also changes (97.0% of the pairs). In 9053 of those pairs both events have the same activity name (68.0%).
FACT: 10427 consecutive pairs are >24 hours, in 2964 cases (98.8%). In 10168 of those pairs the resource identifier also changes (97.5% of the pairs). In 7174 of those pairs both events have the same activity name (68.8%).
FACT: 6670 consecutive pairs are >72 hours, in 2885 cases (96.2%). In 6472 of those pairs the resource identifier also changes (97.0% of the pairs). In 4847 of those pairs both events have the same activity name (72.7%).
FACT: negative timestamp gaps: 0.
FACT: the most common activity pairs around a gap above 24 hours are W_Call after offers -> W_Call after offers (4312), W_Validate application -> W_Validate application (1290), W_Call incomplete files -> W_Call incomplete files (1005), W_Call after offers -> A_Cancelled (753), A_Concept -> W_Complete application (702).
FACT: 4083 workflow occurrences have both a start and a later complete. Wall-clock duration, including any suspend between those two events, has median 1603.42 seconds and 90th percentile 280473.10 seconds.
HYPOTHESIS: a long gap is internal processing, an external wait, or time with no recorded event. The three readings stay open. The gap by itself does not choose among them.

## 6. Repetition and rework

FACT: 1723 cases (57.4%) contain at least one new occurrence of an activity that already occurred.
FACT: cases with a new occurrence, by event origin: Application=1108, Offer=860, Workflow=1325.
FACT: a workflow schedule followed by start, suspend, resume, or complete is one occurrence. Those extra rows are not counted as repetition.
HYPOTHESIS: a new occurrence is rework. The log shows the activity again. It does not show that earlier work was undone.

| Activity | Repeat cases | Adjacent | Separated | Same resource | Different resource |
| --- | ---: | ---: | ---: | ---: | ---: |
| W_Validate application | 1112 | 21 | 1590 | 165 | 1428 |
| A_Validating | 1107 | 0 | 1573 | 163 | 1410 |
| O_Create Offer | 860 | 0 | 1196 | 556 | 640 |
| O_Created | 860 | 0 | 1196 | 556 | 640 |
| O_Sent (mail and online) | 697 | 368 | 572 | 445 | 495 |
| W_Call incomplete files | 529 | 5 | 736 | 333 | 404 |
| A_Incomplete | 529 | 0 | 737 | 333 | 404 |
| O_Cancelled | 400 | 484 | 70 | 486 | 68 |
| W_Call after offers | 327 | 326 | 4 | 0 | 327 |
| O_Returned | 145 | 0 | 146 | 6 | 140 |
| O_Refused | 93 | 126 | 0 | 126 | 0 |
| O_Sent (online only) | 11 | 9 | 7 | 12 | 4 |

## 7. Handoff analysis

FACT: 2992 cases (99.7%) have at least one pair of consecutive events with different resource identifiers. There are 20444 such pairs.
FACT: 14528 of those pairs (71.1%) keep the same activity name. 2930 cases contain at least one such pair. Many of those pairs are successive lifecycle rows of one workflow occurrence.
FACT: among new occurrences, 3182 are opened by the same resource as the previous occurrence and 5963 by a different resource.
INFERENCE: a resource change on the next different activity is the ordinary succession of the log. It is not, by itself, a transfer of one piece of work.
HYPOTHESIS: a resource change inside the same activity, or on a later occurrence, is a handoff. The identifier changed. The log does not say that responsibility was transferred.

## 8. Workflow topology

FACT: collapsed workflow sequences have 69 distinct variants. Full activity sequences, including application and offer names, have 2053 distinct variants.
FACT: 1112 cases (37.1%) return to a workflow activity after a different workflow activity.
FACT: 330 cases (11.0%) place two occurrences of the same workflow activity next to each other.
FACT: 4 cases (0.1%) start one workflow activity while another workflow activity has been started and not yet completed, aborted, or withdrawn.
INFERENCE: successor variety below is a population fact. Inside one case the collapsed sequence still has one next activity. This is not an AND edge.

Most common collapsed workflow sequences:

- 560 cases, length 3: W_Handle leads -> W_Complete application -> W_Call after offers
- 354 cases, length 4: W_Handle leads -> W_Complete application -> W_Call after offers -> W_Validate application
- 320 cases, length 6: W_Handle leads -> W_Complete application -> W_Call after offers -> W_Validate application -> W_Call incomplete files -> W_Validate application
- 243 cases, length 3: W_Complete application -> W_Call after offers -> W_Validate application
- 216 cases, length 2: W_Complete application -> W_Call after offers
- 201 cases, length 5: W_Complete application -> W_Call after offers -> W_Validate application -> W_Call incomplete files -> W_Validate application
- 178 cases, length 5: W_Handle leads -> W_Complete application -> W_Call after offers -> W_Validate application -> W_Call incomplete files
- 103 cases, length 8: W_Handle leads -> W_Complete application -> W_Call after offers -> W_Validate application -> W_Call incomplete files -> W_Validate application -> W_Call incomplete files -> W_Validate application

Most common directly-follows pairs in the collapsed workflow sequence:

- W_Complete application -> W_Call after offers: 2973
- W_Validate application -> W_Call incomplete files: 2156
- W_Call after offers -> W_Validate application: 2085
- W_Handle leads -> W_Complete application: 1939
- W_Call incomplete files -> W_Validate application: 1572
- W_Call after offers -> W_Call after offers: 326
- W_Validate application -> W_Assess potential fraud: 23
- W_Assess potential fraud -> W_Validate application: 17
- W_Validate application -> W_Validate application: 3
- W_Complete application -> W_Shortened completion : 2
- W_Shortened completion  -> W_Call after offers: 2
- W_Call after offers -> W_Shortened completion : 2
- W_Call incomplete files -> W_Assess potential fraud: 1
- W_Assess potential fraud -> W_Call after offers: 1
- W_Complete application -> W_Assess potential fraud: 1

FACT: workflow activities with more than one observed successor: W_Assess potential fraud, W_Call after offers, W_Call incomplete files, W_Complete application, W_Handle leads, W_Validate application.
FACT: workflow activities with more than one observed predecessor: W_Assess potential fraud, W_Call after offers, W_Call incomplete files, W_Complete application, W_Shortened completion , W_Validate application.

## 9. Application, offer, and workflow objects

FACT: cases by event origin: Application=3000, Offer=3000, Workflow=3000.
FACT: 3000 cases have at least one OfferID. 860 cases have more than one distinct OfferID.
FACT: activities that carry an OfferID: O_Created=4196, O_Sent (mail and online)=3880, O_Returned=2222, O_Accepted=1593, O_Cancelled=2067, O_Refused=512, O_Sent (online only)=197.
FACT: Accepted values: true=2886, false=1310. Selected values: true=2076, false=2120.
FACT: non-empty OfferedAmount events: 4196. Accepted, Selected, and OfferedAmount are filled on O_Create Offer.
FACT: decision-like activity names occur in 3000 cases. Event counts: A_Accepted=3000, O_Accepted=1593, A_Cancelled=1002, O_Cancelled=2067, A_Denied=393, O_Refused=512. Case counts: A_Accepted=3000, A_Cancelled=1002, A_Denied=393, O_Accepted=1593, O_Cancelled=1513, O_Refused=386.
INFERENCE: Application, Offer, and Workflow are three object families in this log. OfferID ties some events to an offer object.
HYPOTHESIS: an offer is a decision output, and Accepted is an authority act. The fields record an activity and a flag. They do not record who is allowed to approve.

## 10. DealOS micro mapping

- Application case -> deal object candidate. 3000 cases. INFERENCE.
- Workflow activity occurrence -> task candidate. Collapsed workflow variants: 69. INFERENCE.
- Activity absent from some cases -> optional task is a possible recording. See the activity table. INFERENCE. The log does not supply AND dependencies. HYPOTHESIS that the edges match.
- Timestamp order -> event order. Median duration 18.89 days. FACT as an observation. V1 time is a day index, not these timestamps. INFERENCE that the two clocks are the same object.
- Start then complete -> a duration, not a progress value in [0, 1]. 4083 paired occurrences. FACT.
- New occurrence of the same activity -> not one-shot completion. 1723 cases. FACT that it occurs. HYPOTHESIS that it is rework.
- Return after another workflow activity -> not an acyclic one-shot graph. 1112 cases. FACT.
- Open overlap of two started workflow activities -> concurrent work is visible. 4 cases. FACT. V1 can allocate several ready tasks in one day, so overlap alone does not force a new micro object. INFERENCE.
- OfferID -> no micro object. FACT that the identifier is present. The task DAG does not contain it.

## 11. DealOS macro mapping

- org:resource -> actor identifier candidate. 143 identifiers. INFERENCE. Not a role. HYPOTHESIS that any of them is a department.
- Resource identifier changes between consecutive events -> 20444 pairs. FACT. A handoff, a role change, or an authority change is not in the record. HYPOTHESIS.
- Accept, deny, refuse, and cancel activity names -> observed actions in 3000 cases. FACT. A discrete authority grant is not in the record. HYPOTHESIS.
- Information produced by one system and required by another -> no field. FACT that the field is absent. An information link remains a hypothesis.
- Involvement over time -> the resource set of a case changes across events. FACT as a set of identifiers. The reason codes task_ready, escalation, and information_requirement are not in the log. HYPOTHESIS.
No macro field is filled from this sample. The representation can store an actor and a grant. This log does not identify the grant.

## 12. Representation gaps

| Id | Cases | Share | Current object that fails | Layer | Tag | Recurring | Extension candidate |
| --- | ---: | ---: | --- | --- | --- | --- | --- |
| M1 | 1723 | 0.574 | one-shot monotone task completion | micro | FACT | True | True |

FACT: A new occurrence of an activity inside the same case. Lifecycle rows of one workflow occurrence are excluded.

| M2 | 3000 | 1.000 | a single task DAG | object | FACT | True | True |

FACT: Application events and Offer events co-occur, and offers carry OfferID. The deal graph has no second object.

| M3 | 2964 | 0.988 | a cause for unrecorded time | temporal | FACT | True | False |

FACT: A gap above 24 hours is observed. The log does not say whether it is internal work, an external wait, or time with no recorded event.

| M4 | 2992 | 0.997 | named actor transitions | macro | INFERENCE | True | False |

INFERENCE: Consecutive events name different org:resource values. That is not yet evidence of a handoff, a role, or authority.

| M5 | 2989 | 0.996 | a single progress value in [0, 1] | micro | FACT | True | True |

FACT: Workflow events use suspend, resume, ate_abort, and withdraw. Those are not points on a monotone progress bar.

| M6 | 1112 | 0.371 | an acyclic one-shot task graph | micro | FACT | False | False |

FACT: A workflow activity occurs, other workflow activities occur, and the first activity occurs again.

| M7 | 3000 | 1.000 | a discrete authority grant | macro | HYPOTHESIS | True | False |

HYPOTHESIS: Accept, deny, refuse, and cancel appear as activity names. The log does not name who is allowed to decide.

| M8 | 0 | 0.000 | an information link between systems | observation | HYPOTHESIS | False | False |

HYPOTHESIS: No field records that one system's output is another system's input. Absence here is not evidence that the link exists.

## 13. Candidate model extensions

An extension candidate is a recurring pattern that no current object can say. This pass does not implement any of them.

- M1 (micro): A new occurrence of an activity inside the same case. Lifecycle rows of one workflow occurrence are excluded.
- M2 (object): Application events and Offer events co-occur, and offers carry OfferID. The deal graph has no second object.
- M5 (micro): Workflow events use suspend, resume, ate_abort, and withdraw. Those are not points on a monotone progress bar.

M3, M4, M7, and M8 stay out of the extension list. A gap is real and its cause is unknown. A resource change is real and is not yet a handoff. An accept activity is real and is not an authority grant. An information link is not in the file.

## 14. Evidence, inference, and hypothesis

FACT is a count or a relation present in the event fields.
INFERENCE is a reading of those fields that a second person could reject, such as treating an A_ name as an application object.
HYPOTHESIS is a mechanism the log does not contain: rework, handoff, external waiting, authority, or an information link.
The precomputed epistemic_status on every source row is inference. This report does not copy it.

## 15. Recommended next experiments

### Ten findings

1. FACT: 3000 complete cases and 113903 events, with median duration 18.89 days and median 6.00 resource identifiers.
2. FACT: Application, Offer, and Workflow events co-exist. 3000 cases have both an application event and an offer event. 860 cases have more than one OfferID.
3. FACT: workflow lifecycle is not a single complete mark. Suspend appears in 2989 cases. Counts: complete=45662, schedule=14109, withdraw=2066, start=12130, suspend=20073, ate_abort=7944, resume=11919.
4. FACT: 1723 cases (57.4%) open a further occurrence of an activity. This count excludes extra lifecycle rows of one workflow occurrence.
5. HYPOTHESIS: that further occurrence is rework. The observation is only that the activity occurs again.
6. FACT: 2992 cases change resource identifier between consecutive events. 14528 of 20444 changes keep the same activity.
7. HYPOTHESIS: the same-activity resource change is a handoff. The different-activity change is ordinary succession until a record says otherwise.
8. FACT: 2964 cases have a gap above 24 hours. The activity pair and the resource change are known. The cause is not.
9. FACT: 1112 cases return to a workflow activity after another workflow activity. 4 cases start a second workflow activity while one is still open.
10. FACT: accept, deny, refuse, and cancel are activity names in 3000 cases. No field states an authority relation.

### Five strongest mismatches

- M2 (FACT): Application events and Offer events co-occur, and offers carry OfferID. The deal graph has no second object. Case share 1.000. Extension candidate: True.
- M5 (FACT): Workflow events use suspend, resume, ate_abort, and withdraw. Those are not points on a monotone progress bar. Case share 0.996. Extension candidate: True.
- M1 (FACT): A new occurrence of an activity inside the same case. Lifecycle rows of one workflow occurrence are excluded. Case share 0.574. Extension candidate: True.
- M7 (HYPOTHESIS): Accept, deny, refuse, and cancel appear as activity names. The log does not name who is allowed to decide. Case share 1.000. Extension candidate: False.
- M4 (INFERENCE): Consecutive events name different org:resource values. That is not yet evidence of a handoff, a role, or authority. Case share 0.997. Extension candidate: False.

### Evidence versus hypothesis

The case counts for a further occurrence (M1), a second object family (M2), a gap (M3), a resource-identifier change (M4), suspend and abort (M5), and a return in the workflow sequence (M6) are facts about the log.
Calling M1 rework, M3 an external wait, M4 a handoff, or M7 an authority grant is a hypothesis.
M8 is the fact that an information link is not recorded.

### Micro model

M1 and M5 clear the recurrence rule. They are facts the current micro transition cannot say: completion is one-shot and monotone, and a workflow activity also has suspend, resume, abort, and withdraw. They justify a later controlled screen. They do not justify editing the frozen transition in this pass.
M6, a return to an earlier workflow activity, is the same family of fact as M1 and is present in 37.1 percent of cases, under the half-case rule. It stays in the catalog and is not a separate extension candidate.
M2, the offer object, is also a fact the single task DAG cannot say. A second object is a representation change, not a change to the progress equation, and it is not implemented here.
Optional activities and concurrent open work do not, by themselves, force a micro change. V1 already has optional tasks and can hold more than one ready task.

### Macro model

Nothing in this sample justifies filling or changing the macro record. Resource identifiers can later be stored as actor ids. The log does not name a role, a system boundary, an authority state, or an information link.

### Explicitly not modeled yet

- Rework as a progress reversal.
- External waiting as the meaning of a timestamp gap.
- A handoff mechanism, a role, a department, or an authority grant.
- Information links between systems.
- A customer organization, a champion, strategic behavior, or a probability.
- Any new policy, optimizer, or change to the micro simulator.


---

# BPI17 occurrence birth

A birth is a new occurrence of an activity that already occurred in the same case. Workflow births are a later schedule, or a start when that activity is not already open. Application and offer births are a later completion of the same activity name. The row recorded here is only the event immediately before that birth.

FACT: 9145 births.
A preceding pair is called dominant when it covers at least 50% of an activity's births and that activity has at least 100 births. That bar is a reporting rule. It is not a significance test, and a dominant pair is not an edge.

| Activity | Births | Distinct pairs | Top predecessor | Top lifecycle | Top share | Same resource |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| W_Validate application | 1593 | 7 | W_Call incomplete files | ate_abort | 86.2% | 100.0% |
| A_Validating | 1573 | 1 | W_Validate application | start | 100.0% | 100.0% |
| O_Create Offer | 1196 | 14 | O_Created | complete | 36.7% | 53.9% |
| O_Created | 1196 | 1 | O_Create Offer | complete | 100.0% | 100.0% |
| O_Sent (mail and online) | 940 | 8 | O_Created | complete | 58.0% | 99.6% |
| W_Call incomplete files | 737 | 3 | W_Validate application | ate_abort | 55.9% | 100.0% |
| A_Incomplete | 737 | 1 | W_Call incomplete files | start | 100.0% | 100.0% |
| O_Cancelled | 554 | 9 | O_Cancelled | complete | 87.4% | 99.8% |
| W_Call after offers | 327 | 2 | W_Call after offers | ate_abort | 99.7% | 100.0% |
| O_Returned | 146 | 8 | W_Call incomplete files | suspend | 32.2% | 39.0% |
| O_Refused | 126 | 1 | O_Refused | complete | 100.0% | 100.0% |

FACT: 9 of 11 frequent activities have a dominant preceding pair. The others are O_Create Offer, O_Returned.
The dominant pair is the same activity for O_Cancelled (87.4%), W_Call after offers (99.7%), O_Refused (100.0%). The new occurrence opens after another event of that same activity.
The dominant pair is a different activity for W_Validate application after W_Call incomplete files / ate_abort (86.2%), A_Validating after W_Validate application / start (100.0%), O_Created after O_Create Offer / complete (100.0%), O_Sent (mail and online) after O_Created / complete (58.0%), W_Call incomplete files after W_Validate application / ate_abort (55.9%), A_Incomplete after W_Call incomplete files / start (100.0%).
No pair is written as an edge. Extra-occurrence readiness stays unresolved. The decision layer should keep allocating to the primary occurrence only.

Same-resource share is a count of identical resource ids. It is not a handoff.
This pass does not interpret gaps, authority, information links, or deal completion.

---

# BPI17 occurrence birth context

Each birth is a new occurrence under the existing rule. For k = 1, 3, and 5, the rows are the events immediately before that birth in the same case. The window stops at the start of the case. It does not borrow events from another case.

FACT: a predecessor count is how often that activity and lifecycle sit in the window.
UNRESOLVED: that predecessor causes the birth. A frequent pair is not an edge.

The k = 1 column is the event directly before the birth. The k = 3 and k = 5 shares below are also computed on that immediate event, so a change would mean the birth set itself changed. The named-pattern table then asks whether the same pair appears anywhere in the longer window.

| Activity | Births | k=1 top | k=1 share | k=3 share | k=5 share |
| --- | ---: | --- | ---: | ---: | ---: |
| W_Validate application | 1593 | W_Call incomplete files / ate_abort | 86.2% | 86.2% | 86.2% |
| A_Validating | 1573 | W_Validate application / start | 100.0% | 100.0% | 100.0% |
| O_Create Offer | 1196 | O_Created / complete | 36.7% | 36.7% | 36.7% |
| O_Created | 1196 | O_Create Offer / complete | 100.0% | 100.0% | 100.0% |
| O_Sent (mail and online) | 940 | O_Created / complete | 58.0% | 58.0% | 58.0% |
| A_Incomplete | 737 | W_Call incomplete files / start | 100.0% | 100.0% | 100.0% |
| W_Call incomplete files | 737 | W_Validate application / ate_abort | 55.9% | 55.9% | 55.9% |
| O_Cancelled | 554 | O_Cancelled / complete | 87.4% | 87.4% | 87.4% |
| W_Call after offers | 327 | W_Call after offers / ate_abort | 99.7% | 99.7% | 99.7% |
| O_Returned | 146 | W_Call incomplete files / suspend | 32.2% | 32.2% | 32.2% |
| O_Refused | 126 | O_Refused / complete | 100.0% | 100.0% | 100.0% |

Named patterns, as a share of births of that activity in which the pair appears somewhere in the window:

| Birth | Pair | k=1 | k=3 | k=5 |
| --- | --- | ---: | ---: | ---: |
| A_Incomplete | W_Call incomplete files / start | 100.0% | 100.0% | 100.0% |
| A_Validating | W_Validate application / start | 100.0% | 100.0% | 100.0% |
| O_Cancelled | O_Cancelled / complete | 87.4% | 88.1% | 89.7% |
| O_Created | O_Create Offer / complete | 100.0% | 100.0% | 100.0% |
| O_Refused | O_Refused / complete | 100.0% | 100.0% | 100.0% |
| O_Sent (mail and online) | O_Created / complete | 58.0% | 97.0% | 99.2% |
| W_Call after offers | W_Call after offers / ate_abort | 99.7% | 99.7% | 99.7% |
| W_Validate application | W_Call incomplete files / ate_abort | 86.2% | 86.2% | 86.2% |

A pair is dominant at k = 1 when it covers at least 50% of births and the activity has at least 100 births. That bar is a reporting rule.
No pair is written as an edge, and readiness is unchanged.

---

# BPI17 resource continuity at occurrence birth

The resource field is an observed identifier. A matching id is not ownership. A differing id is not a handoff, a role change, or an authority transfer.

FACT: of 9145 births, 8500 (92.9%) have the same resource id as the immediately preceding event, 645 (7.1%) have a different id, and 0 (0.0%) have a missing id.

Four-way split of the same births:

- FACT: same resource and same activity: 1318 (14.4%).
- FACT: same resource and different activity: 7182 (78.5%).
- FACT: different resource and same activity: 0 (0.0%).
- FACT: different resource and different activity: 645 (7.1%).

Named birth patterns:

| Birth | Preceding event | n | Same resource |
| --- | --- | ---: | ---: |
| W_Call after offers | W_Call after offers / ate_abort | 326 | 100.0% |
| O_Cancelled | O_Cancelled / complete | 484 | 100.0% |
| O_Refused | O_Refused / complete | 126 | 100.0% |
| W_Validate application | W_Call incomplete files / ate_abort | 1373 | 100.0% |
| A_Validating | W_Validate application / start | 1573 | 100.0% |
| A_Incomplete | W_Call incomplete files / start | 737 | 100.0% |
| O_Created | O_Create Offer / complete | 1196 | 100.0% |
| O_Sent (mail and online) | O_Created / complete | 545 | 99.6% |

INFERENCE: where the share is high, the same identifier is present on both events.
HYPOTHESIS: that identifier means the same person continued the work. The log does not say that.

---

# BPI17 lifecycle of repeated occurrences

Occurrence 1 is the first time the activity occurs in the case. Occurrence 2+ is every later occurrence under the same birth rule. Lifecycle rows inside one workflow occurrence are not extra repetitions. Application and offer events are one completion each. Missing transitions are left missing.

Suspend is not labeled as waiting. Abort is not labeled as failure. A repeat is not labeled as rework.

FACT: First occurrences: n=46543, scheduled 24.6%, started 20.8%, suspended 16.9%, resumed 12.4%, completed 82.6%, aborted 13.6%, withdrawn 3.8%. Median lifecycle events 1, p90 6.0. Start-to-complete durations: n=3372, median 987.7 seconds, p90 315708.7 seconds.
FACT: Additional occurrences: n=9145, scheduled 29.1%, started 25.6%, suspended 24.4%, resumed 15.1%, completed 78.7%, aborted 17.8%, withdrawn 3.4%. Median lifecycle events 1, p90 6.0. Start-to-complete durations: n=711, median 19619.4 seconds, p90 256311.8 seconds.

Activities with the most additional occurrences. A cohort under 30 occurrences is marked small.

| Activity | Additional n | First completed | Additional completed | First aborted | Additional aborted | First median events | Additional median events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| W_Validate application | 1593 | 44.7% | 38.2% | 55.3% | 61.8% | 4.0 | 4 |
| A_Validating | 1573 | 100.0% | 100.0% | 0.0% | 0.0% | 1.0 | 1 |
| O_Create Offer | 1196 | 100.0% | 100.0% | 0.0% | 0.0% | 1.0 | 1.0 |
| O_Created | 1196 | 100.0% | 100.0% | 0.0% | 0.0% | 1.0 | 1.0 |
| O_Sent (mail and online) | 940 | 100.0% | 100.0% | 0.0% | 0.0% | 1.0 | 1.0 |
| A_Incomplete | 737 | 100.0% | 100.0% | 0.0% | 0.0% | 1.0 | 1 |
| W_Call incomplete files | 737 | 11.5% | 13.6% | 88.4% | 86.0% | 6.0 | 6 |
| O_Cancelled | 554 | 100.0% | 100.0% | 0.0% | 0.0% | 1 | 1.0 |
| W_Call after offers | 327 | 1.3% | 0.0% | 98.7% | 2.4% | 6 | 2 |
| O_Returned | 146 | 100.0% | 100.0% | 0.0% | 0.0% | 1.0 | 1.0 |
| O_Refused | 126 | 100.0% | 100.0% | 0.0% | 0.0% | 1.0 | 1.0 |
| O_Sent (online only) | 16 small | 100.0% | 100.0% | 0.0% | 0.0% | 1 | 1.0 |

FACT: the percentages are shares of occurrences that contain that lifecycle name.
INFERENCE: a lower completion share on additional occurrences means fewer of those occurrences contain a complete event.
HYPOTHESIS: the additional occurrence failed, waited, or was rework. Those readings are not in the event name.

---

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

---

# BPI17 resource activity profiles

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

---

# BPI17 resource-id transitions

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

---

# BPI17 resource identifiers and lifecycle names

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

---

# BPI17 macro experiment summary

The table has 3000 cases and 113903 events. org:resource is the identifier on the event. No semantic field for person, role, department, owner, or authority is present, so none was substituted.

## 1. What org:resource lets us observe

FACT: an identifier, the activity name, the lifecycle name, the case, and the timestamp.
The field does not say who the identifier is.

## 2. Activity profiles

FACT: median distinct activities 14. Median share in the top activity 0.33. Resources with top share at least 80%: 0.
FACT: resources in at least 30 cases account for 97.5% of events. Among those resources, 67.9% have a stable top-activity share under the 0.10 rule.
INFERENCE: the typical identifier is spread across many activity names.
HYPOTHESIS: the identifier is a generalist employee.

## 3. Transitions

FACT: 5873 directed pairs. The top 1% cover 11.3% of id changes. Concentrated: False. Reverse direction also observed for 3382 directed pairs.
INFERENCE: a low top-1% share means the changes are diffuse.
HYPOTHESIS: a directed pair is an organizational handoff.

## 4. Lifecycle

FACT: 0 resources meet the lifecycle concentration rule. Complete events are common because application and offer rows are recorded as complete.
HYPOTHESIS: presence on a complete row is authority to complete.

## 5. Cross-case persistence

FACT: 109 identifiers appear in at least 30 cases. Median activities per identifier: 14. Identifiers at or above that median: 79.
INFERENCE: many identifiers recur across cases and activities, so they behave like persistent ids in this extract.
HYPOTHESIS: the identifier is a person who owns the work.

## 6. A macro-level entity

Only if the persistence bar is met: resources in at least 30 cases carry at least half of events, and at least half of those resources keep a stable top-activity share. Otherwise the ids are persistent strings with unstable activity mixes, which is not enough to add an entity.

## 7. A macro-level relationship

Only if the top 1% of directed id pairs cover at least half of id changes. Otherwise the transitions do not form a small observed network.

## 8. Facts

The counts in the three reports: activity breadth, top shares, entropy, directed-pair concentration, lifecycle shares, and gap buckets.

## 9. Inferences

A broad activity list means the id is seen on many activity names. A diffuse pair list means changes are spread out. A stable top share means the same activity name remains common inside each case.

## 10. Hypotheses

Person, role, department, authority, ownership, handoff, and waiting. None of these fields exist in the log.

## 11. A new macro primitive

Candidates that met a predeclared bar: persistent resource identifier.
A candidate is a name for a later representation discussion. It is not implemented in this pass.

## 12. If a candidate is named

persistent resource identifier: the id recurs across cases and its top activity share stays within 0.10 of the global share. It would let a later model point at the same id across events. It would not prove a person or a role.
observed resource-id transition: a small set of directed pairs would cover at least half of id changes. It would let a later model store those observed pairs. It would not prove a handoff.

## 13. If no candidate is named

The ids are real and the transitions are real, and both are already describable as fields on events. Unstable mixes and a long pair list do not force a new object.

## Decision

MACRO CANDIDATE IDENTIFIED

Named candidates, not implemented: persistent resource identifier.

---

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
