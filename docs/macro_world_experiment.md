# Macro world experiment

This file is the whole experiment: the worlds, the masks, the representation checks, and the decision.

## 1. Objective

The ground truth is an organizational world, the observation is the part a mask exposes, and the representation is only what the named primitives can express. Hidden ground truth is not copied into the event stream.

## 2. Ground Truth schema

Organization: organization_id.
Deal: deal_id.
Department: department_id, organization_id, name.
Role: role_id, department_id, name.
Resource: resource_id, role_id, resource_type.
System: system_id, name.
TaskType: task_id, name.
TaskOccurrence: occurrence_id, deal_id, task_id, lifecycle, progress.
InformationObject: information_id, name, producer_system_id, consumer_system_ids.
AuthorityRule: authority_id, holder_id, holder_kind, action, scope.
CapacityPool: capacity_pool_id, resource_id, role_id, capacity.
Relations: belongs_to(resource, role), belongs_to(role, department), performs(resource, occurrence), requires(occurrence, information), produces(system, information), consumes(system, information), authorizes(holder, action), allocated_to(resource, occurrence), depends_on(task, task).

## 3. Observation schema

An observation carries event_id and only the fields the mask exposes: timestamp, deal_id, activity, lifecycle, resource_id, system_id, information_id, role_id, department_id, authority, information_link, capacity.
ObservationMask: expose_resource_id, expose_role, expose_department, expose_authority, expose_information_links, expose_system_id, expose_information_id, expose_capacity, expose_deal_id, expose_activity, expose_lifecycle, expose_timestamp.

## 4. Representation R0

R_micro is TaskType, DAG, TaskOccurrence, Lifecycle, Progress, Capacity.
R0 is R_micro plus PersistentResourceIdentifier and ResourceOccurrenceAssociation.
R0 has no Role, Department, Authority, InformationDependency, System, Ownership, or Handoff primitive.
Scenario A starts from R_micro. Scenarios B through G start from R0.

## 5. Scenario definitions

| Scenario | Missing primitive | Initial | Candidate | GT representable | Observable | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| A Resource identity | PersistentResourceIdentifier, ResourceOccurrenceAssociation | R_micro | R1-A | yes | yes | identifier and association are representable and recoverable |
| B Resource to role | Role, ResourceRoleAssociation | R0 | R1-B | yes | no | role is representable only after the mutation and is not recoverable |
| C Department structure | Department, RoleDepartmentAssociation | R0 | R1-C | yes | no | department is representable only after the mutation and is not recoverable |
| D Authority | Authority | R0 | R1-D | yes | no | authority is representable only after the mutation and is not recoverable |
| E Information dependency | InformationObject, InformationDependency | R0 | R1-E | yes | no | information dependency is representable only after the mutation and is not recoverable |
| F Shared resource | none | R0 | R0 | yes | shared_identity yes; capacity_pool no | shared identity is already representable and the capacity value is not recoverable |
| G Multiple interpretations | none | R0 | R0 | no | no | HYPOTHESIS unresolved |

Seed used for timestamps: 0.

Scenario A, Resource identity. The same resource id appears in more than one deal, and the event stream shows that id.

Scenario B, Resource to role. Ground truth links R17 to LegalReviewer. The activity name is PacketCheck, and the mask hides the role.

Scenario C, Department structure. Ground truth groups LegalReviewer under Legal and SecurityReviewer under Security. The mask hides the department.

Scenario D, Authority. FinanceApprover is the only holder of ApproveDeal. Clerk_R2 can appear on that activity and has no authority rule.

Scenario E, Information dependency. CRM produces CustomerProfile, RiskEngine consumes it and produces RiskAssessment, and ApprovalSystem consumes RiskAssessment.

Scenario F, Shared resource. Legal_R1 participates in Deal_1, Deal_2, and Deal_3. One capacity pool has size 1. The pool size is hidden.

Scenario G, Multiple interpretations. R17 appears on LegalReview, ContractReview, and Approval. Ground truth does not choose a role, a delegation, or a shared-resource reading.

## 6. Mismatches

M001 (FACT): The same resource_id appears across multiple occurrences. Missing capability: resource-occurrence identity.
M002 (FACT): A persistent resource id participates. The role is not in the event stream. Missing capability: role representation.
M003 (FACT): Resource ids and activities are exposed. Department membership is not. Missing capability: department representation.
M004 (FACT): Two resources appear on ApproveDeal. The authority rule is not in the event stream. Missing capability: authority representation.
M005 (FACT): System ids are exposed. The produces and consumes links are not. Missing capability: information dependency.
M006 (FACT): One resource id appears in three deals. The capacity number is not in the event stream. Missing capability: hidden capacity value.
M007 (HYPOTHESIS): One resource id appears on three activity names. No role or authority relation is in the ground truth. Missing capability: unresolved interpretation.

## 7. Candidate mutations

Scenario A: AddObject(PersistentResourceIdentifier), AddRelation(ResourceOccurrenceAssociation).
Scenario B: AddObject(Role), AddRelation(ResourceRoleAssociation).
Scenario C: AddObject(Department), AddRelation(RoleDepartmentAssociation).
Scenario D: AddObject(Authority).
Scenario E: AddObject(InformationObject), AddRelation(InformationDependency).
Scenario F: none.
Scenario G: none.

## 8. Validation

Scenario A: accepted True. Schema True. Integrity True. Leakage check True. Regression check True. Alignment True.
Scenario B: accepted True. Schema True. Integrity True. Leakage check True. Regression check True. Alignment True.
Scenario C: accepted True. Schema True. Integrity True. Leakage check True. Regression check True. Alignment True.
Scenario D: accepted True. Schema True. Integrity True. Leakage check True. Regression check True. Alignment True.
Scenario E: accepted True. Schema True. Integrity True. Leakage check True. Regression check True. Alignment True.
Scenario F: accepted True. Schema True. Integrity True. Leakage check True. Regression check True. Alignment True.
Scenario G: accepted True. Schema True. Integrity True. Leakage check True. Regression check True. Alignment True.

## 9. Ground Truth coverage

Scenario A: 1.0.
Scenario B: 1.0.
Scenario C: 1.0.
Scenario D: 1.0.
Scenario E: 1.0.
Scenario F: 1.0.
Scenario G: 0.0.

## 10. Observation recoverability

Representable and recoverable are separate. A candidate can express a ground-truth relation while the mask still hides it.

Scenario A: resource_occurrence_identity recoverable: yes.
Scenario B: role recoverable: no.
Scenario C: department recoverable: no.
Scenario D: authority recoverable: no.
Scenario E: information_dependency recoverable: no.
Scenario F: shared_identity recoverable: yes. capacity_pool recoverable: no.
Scenario G: ambiguous_interpretation recoverable: no.

## 11. Epistemic violations

Scenario A: 0.
Scenario B: 0.
Scenario C: 0.
Scenario D: 0.
Scenario E: 0.
Scenario F: 0.
Scenario G: 0.

## 12. Regression checks

Scenario A: regression false, complexity delta 2.
Scenario B: regression false, complexity delta 2.
Scenario C: regression false, complexity delta 2.
Scenario D: regression false, complexity delta 1.
Scenario E: regression false, complexity delta 2.
Scenario F: regression false, complexity delta 0.
Scenario G: regression false, complexity delta 0.

## 13. Final conclusions

1. Representable relations in the candidate for each scenario: A resource_occurrence_identity, B role, C department, D authority, E information_dependency, F shared_identity.
2. Recoverable from the masked events: A resource_occurrence_identity, F shared_identity.
3. Representable and still requiring evidence: B role, C department, D authority, E information_dependency, F capacity_pool.
4. Mutations justified by the exposed events: A PersistentResourceIdentifier, ResourceOccurrenceAssociation. Representation extensions that the events do not recover: B Role, ResourceRoleAssociation, C Department, RoleDepartmentAssociation, D Authority, E InformationObject, InformationDependency.
5. Unresolved hypotheses: G.
6. The macro candidates add a relation the starting representation lacked in scenarios A, B, C, D, E.
7. Ready for a later problem formulation: A is the resource-occurrence relation. F records one resource id across three deals and a hidden finite pool, with no allocation chosen. B, C, D, and E are schema extensions whose relations are still hidden. G is unresolved.

## Decision

MACRO WORLD VALIDATED
