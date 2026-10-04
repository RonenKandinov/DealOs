# DealOS world map

This document is the organizational map and the rules for promoting a mechanism into the formal model. It does not change the simulator, the policies, the generator, or experiments 0–9. It does not add an observation state, a value objective, an optimizer, or an agent.

Status tags:

- **[OBSERVED]** — measured inside the frozen synthetic V1 screens. This is not a claim about real companies.
- **[TO VALIDATE]** — a concrete coding or screen can accept or reject it. Not yet run on real records.
- **[HYPOTHESIS]** — a candidate description. No evidence yet.
- **[NOT YET MODELED]** — deliberately absent from the formal state.

V1 today (`README.md`, `src/dealos/generator/generate.py`): a deal is an AND-DAG of tasks. Progress, readiness, constant capacities, and `q` (suitability) determine the allocation. Template task types are commercial, technical, legal, security, procurement, and executive. Procurement and executive approval are both suitable only for `ae`. There is no actor, department, authority relation, information object, or time-varying involvement.

The stack Real world → Observations → World representation → Candidate problem → Evidence → Decision model is **[HYPOTHESIS]**. V1 implements only the last box, and only as allocation on a fully observed task state.

## 1. World-model ontology

Start from a mechanism, then ask whether V1 already has an object for it.

- Work package on a deal, ordered by AND predecessors. **[OBSERVED]** as tasks and edges. Chain, hub, and convergence change completion day and blocked steps without a new state variable.
- Shared capacity of a resource type. **[OBSERVED]**. AE and legal capacity move completed-deal counts. Sales engineering moves the day. Security moves the count only at a very low capacity. Solutions architect barely moves the day in the tested band.
- Suitability: a resource type can or cannot be applied to a task type. `q = 0` removes the allocation and does not change the path or the eligible set. **[OBSERVED]**. Suitability is not authority.
- Clock advance of a task with no allocation. **[OBSERVED]** as a different transition from `q = 0`. Showing that wait to Random, FIFO, and Bottleneck did not change the allocation that was actually stepped, because the freed specialist capacity had no other eligible task.
- A progress figure that is not the true progress. **[OBSERVED]** in the experiment layer only. Fresh daily noise and a constant bias are different trajectories. **[NOT YET MODELED]** in the stepped state. Real CRM logs are still required.
- A new predecessor appearing mid-deal. **[OBSERVED]** as a day shift outside the screening band. A downward progress jump of 0.25 at probability 0.20 stayed inside the day band. **[NOT YET MODELED]**.
- An audited human allocation that differs from the model allocation. **[OBSERVED]** as a record. **[NOT YET MODELED]** as a control law.
- Department, role, formal authority, influence, involvement, escalation, information, external actor, organization scale, criticality, and a changing problem type. **[HYPOTHESIS]** and **[NOT YET MODELED]**.

## 2. Department and function map

The list below is a coding vocabulary for enterprise deal execution, **[HYPOTHESIS]**, not a universal org chart. A function enters the formal model only if coded deals show it changing state, feasible actions, or who may act.

- Commercial motion: Sales, SDR/BDR, Sales Engineering, RevOps. V1 has `ae` and `sales_engineer` as capacity. **[OBSERVED]** as capacity only.
- Technical commitment: Solutions Engineering, Product, Engineering, IT/Architecture. V1 folds this into `technical` tasks and two resources (`sales_engineer`, `solutions_architect`). **[OBSERVED]** as capacity. Separate product or engineering actors are **[HYPOTHESIS]**.
- Risk and obligation: Security, Legal, Compliance, Risk, Finance. Security and legal exist as capacity. Compliance, risk, and finance do not. **[HYPOTHESIS]** for the three missing functions.
- Buying side and delivery: Procurement, Customer Success, Implementation, Support. Procurement exists as a task whose only suitable resource is `ae`. That collapse is **[TO VALIDATE]**. Delivery functions are **[HYPOTHESIS]**.
- Direction: Executive leadership. V1 represents `executive_approval` as an optional task the AE can execute. That is the sharpest collapse in the current template. **[TO VALIDATE]**.

## 3. Role taxonomy

A role is a stable bundle of work, **[HYPOTHESIS]**. A person may hold several roles. V1 has neither people nor roles. It has resource types with capacity `C_r`: `ae`, `sales_engineer`, `legal`, `security`, `solutions_architect`.

Candidate roles to code, not to simulate: account executive, SDR/BDR, sales engineer, solutions architect, security reviewer, counsel, procurement lead, finance approver, executive sponsor, customer champion, customer legal, customer security, customer procurement. Internal versus external is part of the code. V1 has no external actor. **[NOT YET MODELED]**.

## 4. Responsibility taxonomy

Responsibility is who handles a domain. **[HYPOTHESIS]**. It is recorded separately from who may approve the domain.

V1’s `q` map records only one related fact: this resource type can add progress to this task type.

### Responsibility coding fields

For each function that appears on a coded deal, fill one row:

- Function
- Domain handled
- Decisions typically faced
- Actions this function can perform
- Information received
- Information produced
- Resources controlled
- V1 resource types the template would use for this work

## 5. Decision-authority taxonomy

Authority is contextual: Authority(role, decision, organization, deal state, context). **[HYPOTHESIS]**. **[NOT YET MODELED]**.

Authority is not stored as a number in [0, 1]. Context, when a record shows that it matters, is a discrete tuple. Candidates to test: size band, strategic flag, financial-exposure band, risk band, exception-to-policy flag, customer-importance band, geography, product, regulatory flag. A context dimension is kept only if coded deals show the same role deciding in one band and escalating in another.

### Authority table fields

Once an event is an actual decision in a record, fill:

- Decision
- Domain
- Responsible role
- Local authority (a state from section 6)
- Approval authority (role, and a state from section 6)
- Escalation condition
- External dependency
- Scope
- Criticality condition
- Context tuple, or “none recorded”

## 6. Discrete authority states

Starting vocabulary, **[HYPOTHESIS]**, to be revised by coding: `none`, `inform`, `recommend`, `propose`, `execute`, `approve`, `override`.

If coding shows these are different events, split them:

- Information rights: `none`, `receive`, `produce`
- Recommendation
- Execution of work
- Approval: `none`, `local`, `conditional`, `exclusive`

Override is an exception event, in the same sense as the existing allocation audit, not a standing rank. **[TO VALIDATE]** whether real records collapse these states.

V1 has none of these states. `q = 0` means the resource cannot add progress. That is suitability, not approval.

## 7. Escalation model

Escalation is a change of who may decide, triggered by a stated condition. **[HYPOTHESIS]**. **[NOT YET MODELED]**.

Candidate triggers to look for: exception to policy, exposure above a band, stalled external party, conflicting recommendations, missing required approver. The record has to show the decision moving to a different role. A longer thread with the same owner stays a non-escalation.

### Escalation coding fields

- Decision that moved
- Role before
- Role after
- Stated trigger
- Context tuple
- Day or date

## 8. Organization-scale model

One template, three layers, **[HYPOTHESIS]**. Four company sizes do not become four simulators.

- OrganizationTemplate: the function list, the decision types, and which authority relations are allowed.
- OrganizationInstance: which functions exist as distinct roles, which roles are the same person, and how long the approval chain is.
- ActiveOrganizationForDeal: the subset involved in one deal at one time.

Scale claim to test: in a small company the same person often both executes and approves; in a large company those are different people and the chain is longer. Specialization, hierarchy depth, role overlap, department count, and delegation are attributes of the instance.

Scale bands for coding: small startup, growing company, mid-market, large enterprise. The band is a label on the instance, not a separate model.

## 9. Deal and organization interaction

`G_D = (tasks, AND edges)` is **[OBSERVED]**. `G_O = (actors, roles, departments, authority, responsibilities)` is **[HYPOTHESIS]** and **[NOT YET MODELED]**.

Relations to code, and to drop if the coding never needs them:

- Task requires a role to execute.
- Task requires an approval from a different role.
- Role can execute an action.
- Role can approve a decision.
- Role influences an outcome and does not own the decision.
- Decision escalates to a role.
- Task is blocked by an external actor.
- Actor provides information.
- Actor controls a resource.

The minimal representation is the subset these coded deals actually use. The current V1 interaction is only “task type is suitable for resource type.”

### V1 task-to-resource map (the comparison target)

From `SUITABLE_RESOURCES` in `src/dealos/generator/generate.py`:

- commercial → `ae` (discovery, qualification, signature)
- technical → `sales_engineer`, `solutions_architect` (technical validation, solution design, integration)
- legal → `legal` (legal review, contract redline)
- security → `security` (security review)
- procurement → `ae`
- executive → `ae` (executive approval)

Template order and AND predecessors: discovery → qualification → technical validation → solution design and security review → legal review → contract redline → integration (after solution design and security review) → procurement (after integration and contract redline) → executive approval → signature. Optional tasks in the template: solution design, security review, contract redline, executive approval.

## 10. Active organization over time

`O_company` is the instance. `O_deal,t` is who is involved on that deal that day. **[HYPOTHESIS]**.

Usefulness test: in a real timeline, the involved set changes, and that change is a different fact from “a task became ready.” If the involved set is only the resource types of the currently eligible tasks, V1 already represents it and no new object is needed.

### Involvement coding fields

For each day or stage on a coded deal:

- Time label
- Roles involved
- Event that added or removed a role
- Whether a V1 task would have become ready at that same moment
- Same fact as readiness: yes or no

## 11. Candidate problem classes

Names only, **[HYPOTHESIS]**. They are not encoded.

Resource bottleneck and dependency bottleneck are the two classes V1 can already express, and both have moved outcomes in the synthetic screens. **[OBSERVED]** as capacity and edges, not as named problem types.

Still untested as distinct classes: authority bottleneck, information bottleneck, external waiting (the transition is **[OBSERVED]** synthetically; the class label is **[HYPOTHESIS]**), missing stakeholder, approval bottleneck, coordination failure, conflicting incentives, strategic escalation, hidden state (the observation effect is **[OBSERVED]** synthetically), organizational mismatch.

A class is real only if coded deals show it recurring and it is not reducible to capacity, edges, or an external clock.

## 12. Problem representation

`P_t = f(world state, deal state, observations)` is **[HYPOTHESIS]**. **[NOT YET MODELED]**.

V1’s implicit problem is fixed: allocate capacity to eligible tasks to raise the count of completed deals. The screens show two synthetic gaps in that implicit problem. The figure the policy sees can change the trajectory. A value label can oppose the completion count when the horizon leaves deals unfinished. Neither gap is a discovered problem class.

Until evidence says otherwise, a deal may have several problems at once, a problem may replace another, and the fitting description may be uncertain. A single blocker is not assumed.

## 13. Evidence and validation strategy

Bottom-up order for every candidate: name the organizational event, give one concrete deal example, state what would be written in a record, propose a discrete code, and only then write a symbol.

Synthetic screens can reject a mechanism or show that an existing object already covers it. They cannot show that a company works that way. Promotion uses the current screening band: completed-deal mean difference 0.25, residual 0.25, completion day 2, idle-despite 0.02. A difference inside that band is reported and is not called statistically significant.

The known-wait screen is the pattern to copy. A mechanism can change the trajectory and still fail as a decision input when the stepped action does not change.

## 14. Real-world data requirements

The smallest useful packet is a set of closed enterprise deals with a timeline. A CRM dump and a CRM integration are not required for this step.

For each deal: company scale band, the functions that touched it, the person or role for each event, the event kind (work, recommendation, approval, escalation, external wait, or information handoff), the deal-size or exception context if authority changed, and the outcome date. A handful of deals can falsify a collapse. A handful cannot estimate frequencies.

Separately, if a CRM export exists: paired snapshots of recorded progress and later true completion, so a fresh draw can be distinguished from a constant bias. That log does not identify departments or authority.

## 15. What can be measured now

Inside the frozen simulator, with no new dynamics: completed deals, completion day, residual, blocked steps, utilization, idle-despite, allocation support, and wasted allocation. Those measures already separate capacity, edges, external clocks, fresh noise, persistent bias, and a new predecessor.

On real records, once coded: whether executor and approver differ, whether the involved set changes, whether an external party advances with no internal allocation, and whether the same role’s authority changes with a discrete context.

## 16. What cannot currently be measured

No real deal corpus is in the repository. See `records/world_map_deal_coding.txt`. Influence without a formal act, hidden state other than a synthetic observation error, conflicting incentives, and strategic importance are not measurable yet. The completion count is not identified as the business objective. At horizon 80 a positive value cannot oppose the completion count, because FIFO finishes every deal. The horizon-40 conflict used labels assigned from FIFO’s own unfinished deals (11 of 48 seeds). Real values are absent.

## 17. What remains a hypothesis

The full stack from observations to a discovered problem. The department list. The authority vocabulary. Contextual authority. The scale claim about specialization versus chain length. `O_deal,t` as more than the resources of the eligible tasks. Multiple simultaneous problem types. Any claim that this ontology is how companies in general are built.

## 18. Minimal mathematical candidates

These stay unwritten until coding forces one of them. **[NOT YET MODELED]**.

- Keep the deal graph, readiness, and the capacity constraint as they are. **[OBSERVED]**.
- If executor and approver differ: an actor set separate from the resource set, plus a discrete authority relation. Approval is then not a task with productivity and suitability.
- If who shows up changes for reasons other than task readiness: a time-indexed involvement set, separate from authority.
- If recorded progress is systematically not true progress: an observation map. The synthetic result says a constant offset and a fresh draw need different maps. Neither is added until a log says which one occurs.
- If an outside party completes a step on a clock: the external-wait transition already screened, still outside `apply_progress`.

No continuous authority score. No game, belief state, or optimizer.

## 19. Promotion criteria

A mechanism enters the formal model only when all of the following hold:

- Coded records show the event. A plausible story does not.
- It changes deal state, the feasible action, who may act, or whether the decision escalates.
- An existing object does not already express it. Edges, `q = 0`, capacity, and an external clock are checked first.
- A controlled screen, with one change and the frozen baseline held fixed, moves an outcome across the current band, or changes the stepped action in the way the known-wait screen asked.
- The discrete representation is fixed before any equation.

Otherwise it stays on this map as a hypothesis. Synthetic movement alone does not promote it. The observation and external-wait results are the examples: they matter, and they are still outside V1.

## 20. Next experiments

No simulator work belongs to this document.

- Evidence coding uses the sheet in the next section. The comparison target is the V1 map in section 9. The result of the first coding pass is `records/world_map_deal_coding.txt`.
- A falsification read of that coding: V1’s representation fails the read if approvals are regularly a different actor from the worker, if the involved set changes without a task becoming ready, or if external parties advance steps with no internal capacity. It survives the read if those events are rare, or if they are already the same fact as a task, an edge, or a capacity limit.
- Only if the coding forces one new object: one later screen, in the experiment layer, with seeds 0–49 and the existing band. That screen is not opened by an empty corpus.
- The CRM bias-versus-noise question stays attached to the observation map. It stays blocked on a log. It is not a reason to build departments.

## Coding sheet

Use one block per deal. Leave a field blank when the record does not contain it. Do not fill a blank from a general story about companies.

```
deal_id:
scale_band:            small_startup | growing | mid_market | large_enterprise | unknown
outcome_date:
source:                record type, or "none"

event:
  time:
  function:
  role:
  side:                internal | external | unknown
  kind:                work | recommendation | approval | escalation | external_wait | information_handoff
  authority_state:     none | inform | recommend | propose | execute | approve | override | unknown
  context:             none recorded, or a discrete tuple
  v1_task_type:        commercial | technical | legal | security | procurement | executive | none
  v1_resource:         ae | sales_engineer | solutions_architect | legal | security | none
  actor_is_v1_resource: yes | no | unknown
  readiness_same_fact: yes | no | unknown
  notes:

responsibility:        section 4 fields, one function per block
authority:             section 5 fields, one decision per block
escalation:            section 7 fields, or "none recorded"
involvement:           section 10 fields, one time label per block
```

After the events, answer four counts:

- Events whose actor is not the V1 resource for that task type.
- Approvals whose approver is not the role that did the work.
- Involvement changes that are not the same fact as a task becoming ready.
- External advances with no internal allocation.

If every count is zero, or there are no events, no new object is forced. Stop. Do not open a screen.

## Final decision gate

1. Already supported, synthetically: the task DAG and AND readiness, capacity, suitability as `q`, discrete daily allocation, topology as edges, and the distinction between a critical path and a controllable task. Also supported as experiment-layer effects, not as V1 state: an external clock, an observation error, a new predecessor, and an override audit.
2. Hypotheses only: departments as more than resource types, discrete authority, influence, involvement, escalation, organization-scale instantiation, a time-varying active organization, problem classes beyond capacity and edges, and problem discovery across candidate models.
3. Investigate next the collapses V1 already baked in: executive approval and procurement executed by the AE, and no external actor. The observation-error gap stays next in line only if coding shows the missing object is the progress figure rather than who may act.
4. Real data would falsify the current representation if the person who approves is regularly not the resource type that V1 lets add progress, if who is involved changes for reasons other than readiness, if outside parties close steps with no internal allocation, or if recorded progress is a persistent bias rather than the true state. Real deal values would separately put the completion count in question as the objective. The synthetic labels have not established that.
5. Smallest next step: code a few real deal timelines against the V1 task-to-resource map and stop. Do not add a variable the coding does not force.

What has to be true for DealOS to be a problem-representation engine: real timelines contain recurring structures that are not already a task graph, a capacity limit, or a suitability zero, and those structures are visible in records well enough to choose among candidate descriptions. Until that coding exists, DealOS is a capacity-and-dependency simulator with a list of open representational questions.

## Macro representation layer

`src/dealos/org/macro.py` is a macro record around the frozen micro model. **[HYPOTHESIS]** as a picture of companies. **[NOT YET MODELED]** as a transition.

The micro objects stay `G_D`, readiness, `q`, `C_r`, and `a_ijr`. The macro record can store systems, roles, actors, discrete authority grants, information links, resource-control rights, escalation rules, and involvement events. `DealTaskBinding` is the bridge from a task type to a system, an executing role, an optional approving role, and required information. `describe_system` reports the roles, grants, incoming information, outgoing information, and escalation rules already stored for one system. `active_roles` replays one deal's involvement log. Neither function writes the company record or the micro state. Involvement reasons include `information_requirement`. The package does not import the simulator, and the simulator does not import the package. No candidate department is loaded by default. Company evolution and problem classes remain outside the record.
