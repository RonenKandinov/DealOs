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
