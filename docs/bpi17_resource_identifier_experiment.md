# BPI17 persistent resource identifier

This file is the whole experiment. R0 is the current micro representation. R1 is that representation plus PersistentResourceIdentifier and a Resource–TaskOccurrence association. The log is BPI17. The simulator and TaskOccurrence are unchanged. No resource-id transition is stored.

## Decision rule

The primitive is justified when three conditions hold together. R1 can represent all three capabilities and R0 can represent none. At least one identifier occurs in two or more cases. R1's case, activity, and event answers match the resource column on the event, the R1 objects have no role or capacity fields, and no transition pair is stored.

## What each representation holds

R0 TaskOccurrence fields: occurrence_id, deal_id, task_id, lifecycle, progress, offer_id, readiness_source.
R0 Resource fields: resource_id, resource_type, capacity. That object is a capacity pool. The log has no capacity and no resource type for org:resource.
R1 PersistentResourceIdentifier fields: resource_id.
R1 ResourceOccurrenceAssociation fields: resource_id, occurrence_id.
An event index is kept only as a counter of log rows that support a pair. It is not an object in R1.

## Log counts

FACT: 113903 events, 3000 cases, 55688 occurrences.
FACT: 143 distinct org:resource strings, 74979 resource–occurrence pairs.
FACT: 141 identifiers appear in two or more cases. 2 appear in one case.
FACT: 0 events have an empty resource id. 0 workflow events fall outside the existing occurrence rule.
FACT: 11143 occurrences contain two or more distinct resource ids. Each id is its own pair. The pairs are not a transition.
FACT: R1 matches the event column on every identifier: True.

## Cross-case identity

Can the representation state that the same org:resource identifier appears in more than one case?

Representable in R0: no.
Representable in R1: yes.
New object-level relation when both can represent it: not applicable.
FACT: 141 of 143 identifiers appear in two or more cases, covering 113889 events. R0 occurrences have no resource field, and R0 Resource does not record case membership. R1 keeps one PersistentResourceIdentifier per string, and the case set is read from the associations.
Epistemic status: FACT.

## Resource-occurrence association

Can the representation state an explicit Resource to TaskOccurrence pair with no further semantics?

Representable in R0: no.
Representable in R1: yes.
New object-level relation when both can represent it: not applicable.
The Resource–TaskOccurrence pair is an object in R1.
FACT: 74979 pairs. FACT: 11143 occurrences have more than one resource id, stored as separate pairs. R0's only resource-bearing triple is an allocation amount, which is a capacity fraction, so it is not this pair. R1's association has resource_id and occurrence_id.
Epistemic status: FACT.

## Persistence queries

Can the representation answer which cases, which activity names, and how many occurrences and events belong to resource r?

Representable in R0: no.
Representable in R1: yes.
New object-level relation when both can represent it: not applicable.
FACT: R1 matches the resource column for cases, activity names, and events: True. R0 returns no case list, no activity list, and no count. The occurrence count is the number of pairs for that id.
Epistemic status: FACT.

## Persistence query check

The three R1 answers were compared with a direct read of the resource column: cases, activity names, and events. Occurrence counts use the existing occurrence rule.

| Resource id | Cases | Activity names | Occurrences | Events |
| --- | ---: | ---: | ---: | ---: |
| User_1 | 2245 | 11 | 12045 | 13949 |
| User_3 | 573 | 19 | 1479 | 2463 |
| User_5 | 546 | 19 | 1415 | 2307 |
| User_87 | 422 | 22 | 1034 | 2100 |
| User_30 | 370 | 21 | 1130 | 2092 |
| User_29 | 307 | 21 | 1262 | 2006 |
| User_123 | 298 | 9 | 1255 | 1957 |
| User_100 | 350 | 21 | 1173 | 1920 |
| User_2 | 456 | 21 | 1061 | 1909 |
| User_49 | 385 | 16 | 1207 | 1896 |
| User_28 | 362 | 18 | 1179 | 1874 |
| User_68 | 260 | 20 | 963 | 1799 |
| User_121 | 290 | 9 | 1143 | 1770 |
| User_27 | 278 | 19 | 1095 | 1680 |
| User_116 | 279 | 9 | 1076 | 1651 |

The table shows the 15 identifiers with the most events. All 143 identifiers are in the csv.

## Epistemic limit

FACT: the identifier is the org:resource string, and the association is the pair of that string with an occurrence id.
The objects do not carry a person, a role, a department, ownership, authority, a handoff, or a responsibility.

## Decision

MACRO PRIMITIVE JUSTIFIED
