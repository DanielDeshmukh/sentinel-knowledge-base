# Synthetic Security Architecture Notes

> SYNTHETIC: for demonstration only

## Demonstration topology

All names and addresses below are documentation-only examples.

| Segment | Reserved example range or host | Purpose |
| --- | --- | --- |
| Edge | `198.51.100.0/24` | Public-facing demonstration ingress |
| Application | `192.0.2.0/24` | Stateless service instances |
| Data | `203.0.113.0/24` | Restricted data services with no direct public route |
| Example host | `portal.example.com` | Human-readable placeholder for the portal |

## Trust boundaries

External requests terminate at a managed edge. The application tier accepts only approved service traffic. Data services are reachable only from authorized application identities over encrypted connections. Administrative access uses a separate restricted path with multifactor authentication and audited approvals.

## Security notes

- Keep secrets in an approved secrets manager; do not place them in images, logs, or configuration examples.
- Restrict outbound access to documented business needs.
- Collect authentication, administrative, and data-access events in a protected logging service.
- Test backup restoration and access revocation in the demonstration environment.

The topology is fictional and must not be used as a production design without a separate threat model and architecture review.
