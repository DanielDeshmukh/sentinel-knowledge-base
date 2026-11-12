# Synthetic Penetration Test Findings

> SYNTHETIC: for demonstration only

## Assessment context

This fictional assessment covers the Example Organization demonstration portal and its supporting service boundary. It uses no real target, credential, exploit payload, or external system.

## Findings

| ID | Severity | Observation | Recommended action |
| --- | --- | --- | --- |
| F-01 | High | A sample administrative workflow grants broader read access than its stated business purpose. | Enforce role-based authorization at each service boundary and add negative-access tests. |
| F-02 | Medium | Session revocation is not consistently reflected across all demonstration service replicas. | Use a shared revocation mechanism, define expiry behavior, and test account disablement. |
| F-03 | Medium | Audit events omit the actor role for selected administrative changes. | Include a stable actor identifier, role, action, result, and timestamp in protected audit records. |
| F-04 | Low | Error messages reveal whether a fictional record identifier exists. | Return consistent external errors and retain diagnostic details only in restricted logs. |

## Verification and remediation

Owners should reproduce each observation only in the isolated demonstration environment, implement the listed correction, and attach a passing regression test or review record. The assessment does not establish that any real service was tested.
