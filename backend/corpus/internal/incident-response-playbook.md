# Incident Response Playbook

> SYNTHETIC: for demonstration only

## Roles

The Incident Lead coordinates decisions and status. The Security Lead directs technical triage. The System Owner explains business impact and recovery needs. The Communications Lead prepares approved internal and external updates.

## Response sequence

1. **Report and record:** Capture the time, reporter, affected service, observed impact, and immediate safety concerns.
2. **Triage:** Assign an incident identifier, assess severity, identify affected assets and data classes, and select the response roles.
3. **Contain:** Use the least disruptive effective action to limit further impact. Record approvals and preserve evidence before changing system state when practical.
4. **Investigate and remediate:** Establish a working timeline, identify the likely cause, remove the condition that enabled the incident, and validate the changes.
5. **Recover:** Restore from verified sources, monitor for recurrence, and confirm service-owner acceptance.
6. **Communicate and review:** Provide updates through approved channels, record decisions, and assign improvements with owners and due dates.

## Data exposure and external reporting

If personal data or a regulated service may be affected, notify the Security Lead and privacy contact immediately. They determine applicable notifications with qualified counsel and the relevant service owner. Do not infer deadlines from this synthetic playbook.

For general preparation, see the public corpus summaries for NIST SP 800-61 Rev. 3 and CERT-In incident reporting. Those summaries do not decide whether a real incident is reportable.

## Evidence and closure

Restrict incident records to authorized responders. Preserve relevant logs and evidence under the organization's approved retention and legal-hold procedures. Close an incident only after recovery is accepted and follow-up work is assigned.
