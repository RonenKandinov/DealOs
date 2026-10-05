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
