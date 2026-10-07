# Macro operating model

The organizational state is a value, not a paragraph. At time t,

O_t = (Structure_t, Resources_t, Capacity_t, Responsibilities_t, Decisions_t, Authority_t, Information_t, Governance_t, Escalations_t, Processes_t, Systems_t, ExternalRelations_t, Time_t)

and

O_(t+1) = F(O_t, E_t)

E_t is one explicit event. There is no second meaning hidden inside an event. A resource id is not a person. A role is not authority. Participation is not a grant. A resource-id change is not a handoff. A time gap is not waiting.

The frozen micro step is unchanged. A configured TaskConstraint names the macro requirements of one task. The gate reads micro readiness as an input and does not rewrite the readiness formula.

## Components

Structure is organizations, departments, and roles, plus first-class relations resource_role, role_department, and department_organization.

Resources are ids. Capacity pools have total and available. holds_capacity is written only by an Allocate event.

Responsibilities are stored statements. They are not implied by a role.

Decisions have status open, approved, rejected, or escalated. An AuthorityGrant names a holder kind (role, resource, or governance), a holder id, and a decision id. Delegation and Veto are their own records.

Information objects are available or not. produces links a system to an information object only when ProduceInformation runs.

Governance bodies, escalation rules, escalations, SLAs, processes, systems, and external relations are separate maps.

## Transitions

Allocate(pool, amount, holder) requires 0 ≤ amount ≤ available, then available decreases.

Release adds the amount back, capped by total.

ProduceInformation marks the object available and stores produces.

ConsumeInformation requires availability, then clears it.

ReceiveExternalInformation marks the information named by that external relation available. Until that event, a task constrained by the relation cannot progress.

Approve and Reject require eligibility: a matching grant or an active delegation, and no active veto. If the actor is not eligible and a rule with condition authority_unavailable exists, the decision becomes escalated. A veto blocks even a granted holder.

Delegate stores delegates(from, to). IssueVeto stores an active veto.

Tick(t) sets time to t. An open subject whose deadline is reached becomes breached, and a rule with condition sla_breached opens an escalation.

Participate(resource, activity) may record the resource. It does not add a grant and does not add a handoff.

## Macro effect on a ready task

Given ready from the micro model and a TaskConstraint,

- not ready → not_ready
- required pool available = 0 → capacity_unavailable
- required external information unavailable → external_information_unavailable
- required information unavailable → information_unavailable
- active veto on the required decision → veto
- no eligible holder and no active delegate → authority_unavailable
- otherwise → can_progress

The micro update x(t+1) = min(1, x + Δx) is not edited. The seed-0 FIFO fingerprint remains 2 completed deals in 40 steps.

## Entities from the operating-model document

These are stored separately. A relation is added only by an explicit event or constructor.

- Organization is a boundary. `external` means outside that boundary. It is not a customer, partner, or vendor type.
- BusinessUnit belongs to an organization and is not a department.
- Department is a functional unit. Membership is not authority.
- Team is its own record and is not a department.
- Person is not a resource. `AssignRole` writes `holds_role` and does not create a resource.
- Role is not a person.
- Capability is what an entity can do. `AssignCapability` writes `has_capability` and does not write responsibility.
- Responsibility and Accountability are different records. `accountable_for` is its own relation.
- DecisionRight kinds are recommend, input, advise, agree, decide, approve, veto, and execute. Granting one does not create an AuthorityGrant.
- AuthorityGrant is the formal holder of a decision. Approval is the Approve event. Veto is a separate active record.
- ExternalRelation.kind and context_id say how one outside organization relates in one context. The same organization id can appear in two relations with different kinds.

The state tuple is

O_t = (Structure_t, Resources_t, Capacity_t, Responsibilities_t, Decisions_t, Authority_t, Information_t, Governance_t, Escalations_t, Processes_t, Systems_t, ExternalRelations_t, Time_t)

Structure includes organizations, business units, departments, teams, people, and roles. Decisions include decision rights. Authority includes grants, delegations, and vetoes. Escalations include rules, open escalations, and SLAs.

O_(t+1) = F(O_t, E_t) for one explicit event E_t. A task constraint is the only configured link from that state to a micro task id.

The optimizer and the representation-evolution loop are not part of F. Co-occurrence, event order, and activity names do not create relations.
