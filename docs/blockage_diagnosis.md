# Blockage diagnosis

Micro is asked where a deal is blocked. Macro is asked why. The two layers are not joined.

Micro V1 fingerprint, seed 0 FIFO, 2 completed deals in 40 steps: True.

| Scenario | Category | Ambiguity | Mutation accepted | Status |
| --- | --- | --- | --- | --- |
| capacity | partially_representable | False | False | FACT |
| information | genuine_gap | False | False | HYPOTHESIS |
| authority | ambiguous | True | False | HYPOTHESIS |
| cross_organization | genuine_gap | False | False | HYPOTHESIS |
| negative_resource_pair | ambiguous | True | False | HYPOTHESIS |
| negative_no_relation | ambiguous | True | False | HYPOTHESIS |
| negative_approval_authority | ambiguous | True | False | HYPOTHESIS |

## Readings

capacity: deal_A:A1 is ready, its progress does not move, and ae is fully used. The macro capacity pool is not attached to this task.
information: Micro readiness is predecessor progress. It does not name a missing information object. Macro can store that a system produces an information object. That link does not name a deal task.
authority: An approval task can still receive allocation. Participation is enough for progress. Macro does not treat the ApproveDeal activity as an authority rule.
cross_organization: A deal graph has no organization endpoint. A department belongs to an organization inside the macro graph only.
negative_resource_pair: Both resource ids are visible. collaborates_with, substitutes_for, and depends_on stay undistinguished.
negative_no_relation: Two resources appear together. No ground-truth relation is invented from that co-presence.
negative_approval_authority: ApproveDeal is visible for two resources. The activity does not establish who may authorize it.

No new primitive is added. The capacity diagnosis is one micro reading: the task is ready, its progress does not move, and the shared resource is fully used. The macro capacity pool is not attached to that task. Information, authority as a gate, and a deal that crosses organizations stay gaps. Co-occurrence is not a relation type, and ApproveDeal is not authority.

The current representation does not yet show, in one model, where an enterprise deal is blocked and why.
