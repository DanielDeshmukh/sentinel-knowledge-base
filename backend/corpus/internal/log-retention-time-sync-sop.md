# Log Retention and Time Synchronization SOP

> SYNTHETIC: for demonstration only

## Purpose

Example Organization uses protected, time-consistent logs to investigate events and support service recovery. System Owners document which systems are covered, what events are recorded, and who can review them.

## Logging and access

- Record security-relevant authentication, administrative, configuration, and data-access events where supported.
- Do not place passwords, recovery codes, access tokens, or unnecessary personal data in logs.
- Restrict log access to authorized operators and responders; record administrative access to logging systems.
- Protect logs against alteration and use approved backups or central collection for critical systems.

## Retention

For this demonstration, retain covered security logs for a rolling 180 days unless an approved schedule, legal hold, or applicable requirement specifies otherwise. System Owners document the storage location, deletion method, and backup expiry. Before applying the schedule to a real service, verify the scope and current requirements; the public CERT-In summary describes the 180-day rule and its stated coverage.

## Time synchronization

Synchronize system clocks to an approved time source and monitor for drift. Document the source, service owner, and alert threshold. Where the CERT-In Directions apply, follow their specified source requirements.

## Review and incidents

Review logging coverage and retention at least annually and after material changes. During an incident, preserve relevant records under the approved evidence procedure and record any retention hold or early deletion exception.
