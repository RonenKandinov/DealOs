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
