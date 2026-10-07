# Macro state experiment

O_t is the organizational state in `dealos.org.operating`. One explicit event produces O_(t+1). A TaskConstraint is the only link from a macro requirement to a micro task id. The simulator formula is not called by these checks.

| Check | Result |
| --- | --- |
| Ready task, capacity available | can_progress |
| Same task, pool exhausted | capacity_unavailable |
| Capacity released | can_progress |
| Information unavailable | information_unavailable |
| Information produced | can_progress |
| Authorized holder | decision approved |
| Holder unavailable and an escalation rule exists | decision escalated |
| Delegation to another holder | that holder can approve |
| Veto while a grant exists | veto, and the grant holder cannot approve |
| Time reaches the SLA deadline | SLA breached and an escalation opens |
| External information not received | external_information_unavailable |
| External information received | can_progress |
| Two Participate events | no handoff relation and no new authority grant |

The micro seed-0 FIFO fingerprint remains 2 completed deals in 40 steps.

## Decision

MACRO STATE IMPLEMENTED
