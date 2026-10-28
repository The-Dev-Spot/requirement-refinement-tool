# Synthetic step catalog

Prefer domain-observable behavior to UI choreography. These wording examples
are not new requirements and contain no inherited business rules.

- Given the requester is authorized to view the requirement
- When the requester submits the reviewed requirement
- Then exactly one requirement is created with the approved content
- Given the source revision has changed since approval
- When publication is requested
- Then publication is rejected and a new review is required
