# BPI17 → DealOS: first empirical profile

## Scope
- Complete cases: 3,000
- Events: 113,903
- Activities: 25
- Resources: 143
- Events carrying OfferID: 14,667

## Case structure
- Median events/case: 35.0
- P90 events/case: 59.0
- Maximum events/case: 148
- Median distinct resources/case: 6.0
- P90 distinct resources/case: 11.0
- Maximum distinct resources/case: 24
- Median observed case duration: 18.89 days
- P90 observed case duration: 35.40 days
- Cases with repeated activities: 3,000
- Cases with at least one resource handoff: 2,992
- Cases with a >24h timestamp gap: 2,964
- Cases with >1 offer event carrying OfferID: 3,000

## First DealOS mapping
| Source pattern | Candidate representation | Status |
|---|---|---|
| A_* activity | Application object/state event | inference |
| O_* activity | Offer object/state event | inference |
| W_* activity | Task candidate | inference |
| org:resource | Actor/resource candidate | inference |
| timestamp | event ordering / elapsed time | observation |
| lifecycle:transition | activity lifecycle | observation |
| repeated activity | possible rework candidate | hypothesis |
| resource change | possible handoff candidate | hypothesis |
| long timestamp gap | possible waiting candidate | hypothesis |

## Important constraint
This package does **not** modify the DealOS core model. The mapping is an adapter/observation layer only. It deliberately does not infer authority, dependency, blocking, causality, or organizational roles from resource IDs alone.

## Next empirical test
Use the normalized event table to identify recurring structures:
1. repeated activities;
2. resource handoffs;
3. long gaps;
4. multiple offers;
5. branching/rejoining patterns;
6. application/offer/workflow interactions.

Only recurring mismatches should motivate a change to Micro or Macro.
