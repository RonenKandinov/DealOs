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
