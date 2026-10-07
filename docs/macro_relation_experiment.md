# Macro relation experiment

### Evaluation summary

- 5 hidden facts
- 7 ambiguous relations
- 3 rejected relations

### Recoverability screen

- 5 hidden facts
- required fields opened
- MR-A resource_role: expose_role
- MR-B role_department: expose_role, expose_department
- MR-C department_organization: expose_organization
- MR-G system_produces_information: expose_information
- MR-H information_consumed_by_system: expose_information
- recoverable after: yes
- type uniqueness preserved: yes

### Safety

- leakage: 0
- regressions: 0
- epistemic violations: 0
- tests: 165 passed

### Decision

FIVE HIDDEN FACTS RECOVERABLE WHEN THEIR OWN FIELDS ARE EXPOSED
