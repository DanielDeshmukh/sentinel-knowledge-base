# Sentinel Knowledge Base

Sentinel is a role-aware knowledge system for cybersecurity and data-protection material. It lets authorized users ask questions across a curated corpus, inspect source passages behind answers, and see retrieval and response timing. Administrators can add records through the application and observe validation, embedding, database synchronization, and search availability.

The product is designed around a clear boundary: the language model receives only passages that the requesting user's current role is permitted to retrieve. A fluent answer is not treated as evidence by itself; responses are grounded in retrieved passages and accompanied by citations. When the authorized corpus has no sufficiently relevant material, the system returns a no-answer response instead of inventing a source.

## Product capabilities

| Capability | Product behavior |
| --- | --- |
| Permission-aware chat | Embeds the question, applies role restrictions in the vector query, and returns relevant passages with citations. |
| Follow-up questions | Uses recent conversation history to resolve references such as “why was it enforced?” while retrieving against the authorized corpus. |
| Document library | Lists searchable documents visible to the signed-in role. |
| Administrator ingestion | Accepts Markdown, PDF, and DOCX uploads up to the configured size limit; the current application limit is 4 MB. |
| Ingestion progress | Reports parser, normalization, chunking, embedding, staging, commit, and searchable status. A failed embedding or validation run does not mark the document searchable. |
| Access administration | Lets administrators review accounts and role requests, and assign the final role. |
| Response timing | Displays retrieval and total response time for chat requests. |

## System overview

The application has a React and TypeScript web client, a FastAPI service, PostgreSQL with pgvector, and hosted model APIs. PostgreSQL stores account and document metadata, chunks, role grants, ingestion jobs, and vectors. The embedding service is configured with NVIDIA; chat generation can be configured for NVIDIA or Groq. Ingestion and query-time retrieval use the same configured embedding model and vector dimension so that stored vectors and query vectors share an embedding space.

The corpus has 25 checked-in records: 11 public, 8 internal, and 6 restricted. Checked-in evaluation fixtures are kept separate from user-created runtime records. Evaluation questions are test data; they are not corpus documents and are not ingested into chat.

## Identity and role model

Sentinel has four account roles. Public, internal, and restricted are ordered access tiers; administrator is a privileged management role.

| Role | Searchable document classifications | Administrative capabilities |
| --- | --- | --- |
| Public | Public | None |
| Internal | Public and internal | None |
| Restricted | Public, internal, and restricted | None |
| Admin | Public, internal, and restricted | Ingest and delete documents; review accounts and role requests; assign roles |

New registrations receive public access immediately. The registration form can include a requested higher role, but the request does not grant that role. An administrator reviews it and makes the final assignment. The registration flow does not create administrator accounts.

### How authorization is enforced

Authorization is enforced by the backend, not by hiding frontend links:

1. A user signs in and receives a signed bearer token. Each protected API request validates that token and loads the user's current account and role from the database.
2. For ingestion, account management, and document deletion, the API requires the database-loaded role to be `admin`. A client-side route or a manually constructed request cannot grant these capabilities.
3. The selected document classification is converted into an explicit `allowed_roles` list on each chunk. Public chunks are available to all four roles; internal chunks are available to internal, restricted, and admin; restricted chunks are available to restricted and admin.
4. The chat vector-search SQL applies the caller's role filter in the same query that ranks vectors by similarity. Disallowed passages are excluded before they can be passed to the language model.
5. Document listings and direct document reads apply classification checks too. A hidden document is returned as not found to a user who cannot access it, rather than revealing that a higher-classification record exists.
6. The application returns the same generic no-answer response when authorized material is absent. This avoids confirming the existence of inaccessible material.

The role hierarchy is intentionally a single ladder for this product. It does not model peer departments with separate, non-overlapping access groups.

## Corpus and classification

The checked-in corpus combines public summaries of primary sources and original synthetic operating documents. Public material includes DPDP Act and Rules summaries, CERT-In and NIST references, CISA playbooks, an independently written ISO/IEC 27001 overview, and security-awareness guidance. Internal and restricted records are fictional demonstration policies, procedures, assessments, and incident records.

Classification controls which user roles can retrieve a document; it is not a claim that a cloud provider, model provider, or deployment environment meets a particular compliance certification. Public summaries are informational and are not legal advice. Confirm current primary sources and applicability before making legal or operational decisions.

## Administrator document ingestion

An administrator uses **Ingestion** in the application. The interface collects a title, classification, provenance or synthetic metadata, and a Markdown, PDF, or DOCX file. The application uses the same canonical backend parser for uploaded records and checked-in corpus validation.

The synchronization lifecycle is:

1. Check upload type and size, then extract text from the file.
2. Run corpus metadata and content rules, including heading structure, control characters, unsafe markup, sensitive-data patterns, and classification-specific provenance rules.
3. If normalization can safely correct a content-format issue, normalize and run the rules again. Unresolved diagnostics stop the ingestion before the record becomes searchable.
4. Split valid content into chunks and generate embeddings with the configured embedding service.
5. Write vectors to staging, then promote the complete set to the searchable chunk table in a database transaction.
6. Mark the document searchable only after the vector rows have been committed. The selected classification determines each chunk's allowed roles immediately.

The progress panel reports the stage, counts, timings, validation diagnostics, and terminal status. If parsing, validation, or embedding fails, the interface reports failure; it must not present the record as available in chat. A retry is safe for identical content because ingestion checks for existing searchable content and reuses it.

### Adding synthetic demonstration content

Use synthetic content for internal or restricted demonstration records. Mark the **synthetic content** option, use the exact label below in the synthetic-label field, and provide the reuse-basis statement in the reuse-basis field. Synthetic records do not need source URLs or a retrieved date. Do not use real people, organizations, customer records, credentials, or production incident details in demonstration content.

Synthetic label — copy exactly:

```text
SYNTHETIC: for demonstration only
```

Reuse basis — copy for original synthetic demonstration material:

```text
Original synthetic demonstration content, independently authored for ingestion testing; no real organization, account, or production environment is represented.
```

The document body must also contain the exact synthetic label. The parser may insert it during normalization when the synthetic metadata is set, but administrators should include it explicitly so the record is unambiguous when read or exported.

### Adding real, source-derived material

Under the current ingestion policy, use the **Public** classification for real source-derived material. Leave the synthetic option off, include the source URL or URLs, enter the retrieval date, and describe the reuse basis. The reuse statement should identify what the administrator authored and what source material or license supports its use; a URL alone does not establish reuse rights. Prefer original summaries and permitted excerpts, and do not upload paid standards or copyrighted source text without authorization.

Internal and restricted uploads are required to be synthetic in the current demonstration policy. Real confidential, personal, or production security data must not be uploaded through this demo flow. The classification selector determines retrieval access; it does not sanitize content or create legal authorization to process it.

## Evaluation set

[`backend/evaluation/questions.v1.jsonl`](backend/evaluation/questions.v1.jsonl) contains 30 version-controlled evaluation cases grounded in the checked-in corpus. Each case identifies a target role, expected answerability, expected source paths, evidence points, and access-denial behavior where applicable. The set covers direct facts, procedural questions, cross-document synthesis, unsupported questions, and public/internal denial probes for higher-classification content.

The questions are a curated evaluation fixture, not an evaluation report. No accuracy or latency results are implied by the presence of the set. A measured report requires a recorded run against a known corpus and model configuration.

## Data handling and operational boundaries

- Do not put passwords, API keys, bearer tokens, or database connection strings in documents, evaluation records, screenshots, or issue reports.
- The parser checks for common sensitive identifiers and suspicious content patterns; those checks reduce risk but do not replace human review or data-loss-prevention controls.
- External model APIs receive question and retrieved passage content required to provide the service. Use only content permitted for the configured provider and deployment. The demo has not been represented here as certified for regulated or confidential production data.
- Public legal and standards summaries can become stale. The corpus records source URLs and provenance for public records; reviewers should verify the current primary source before relying on them.
- A successful ingestion means the vectors were committed and the document is searchable for its allowed roles. It is not an approval of the source's legal status, accuracy, or classification.

## Project quality and scope

Sentinel demonstrates role-filtered retrieval, auditable ingestion progress, citations, and role administration. It is not a legal-advice service, a certification, a substitute for an organization's identity governance or incident-management process, or evidence of a completed security assessment. Production adoption requires environment-specific threat modeling, privacy review, provider and retention review, operational monitoring, backup and recovery planning, and independent security testing.
