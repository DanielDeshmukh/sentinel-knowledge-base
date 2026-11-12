# Access Control and Authentication Standard

> SYNTHETIC: for demonstration only

## Identity and access

Example Organization assigns each user a unique identity. System Owners grant only the access needed for an approved task and record the request, approver, scope, and expiry where applicable. Shared user accounts are not permitted.

Access is removed promptly when a user's role ends or changes. System Owners review privileged and restricted-data access at least quarterly and other access at least annually.

## Authentication

- Use a password manager and a unique password for each account.
- Enable multifactor authentication for remote access, administrative accounts, and services containing restricted information.
- Prefer phishing-resistant methods for privileged access where supported.
- Never send passwords, recovery codes, or authentication tokens in messages or store them in source code.
- Change a credential promptly if compromise is suspected or confirmed; do not rely on routine rotation as a substitute for strong authentication.

## Privileged access

Administrative work uses a separate privileged identity where the system supports it. Privileged actions are logged and reviewed. Emergency access is time-limited, approved after use if necessary, and reviewed by the Security Lead.

## Service accounts and secrets

System Owners document the purpose and owner of each service identity, restrict its permissions, and store its credentials in an approved secrets manager. Credentials are rotated when access is no longer needed or exposure is suspected.

## Exceptions

An exception records the affected system, business reason, compensating safeguards, approver, and expiry date. The Security Lead reviews overdue exceptions.
