# Shared Corpus Parser and Live pgvector Sync

## Status

Design approved by the project owner on 13 November 2026. This document describes one vertical slice: validate and ingest corpus items through a single backend parser, persist a complete corpus record, and show live PostgreSQL/pgvector synchronization through the admin UI. Implementation has not started.

## Goal

An administrator can add a Markdown, PDF, or DOCX corpus item from the frontend. The backend applies the same metadata and regex rules used by the checked-in corpus validator. The UI shows validation, normalization, chunking, embedding, vector writes, promotion, and final searchable status as they happen. Once the promotion transaction commits, a user with an allowed role can retrieve the new chunks from the chat interface and open their citations.

Frontend-added items are runtime database records. They do not edit or change the counts of the checked-in evaluation manifest.

## Current state

- `backend/corpus/validate.py` validates checked-in Markdown and its JSON manifest. It owns some of the current sensitive-data patterns.
- `backend/services/ingestion.py` separately extracts Markdown, PDF, and DOCX, runs the current ingestion gates, creates chunks, calls NVIDIA embeddings, and stages/promotes chunk rows.
- `POST /api/ingest` is admin-only, but returns its stage list only after ingestion finishes.
- `frontend/src/components/admin/IngestionPanel.tsx` submits a file and renders stages after the response returns. It has no live vector-write progress.
- `documents` stores title, classification, source, uploader, and creation time. `chunks` and `staging_chunks` store pgvector vectors and role lists. Chat already applies the allowed-role condition in the SQL vector query.

## User-facing behavior

1. An admin enters title, classification, and corpus provenance, then selects a Markdown, PDF, or DOCX file.
2. The admin UI starts ingestion and receives ordered progress events while the server processes the request.
3. Each validation failure is shown by rule name and line number. Matched sensitive values are never returned or stored in diagnostics. If the file needs normalization, the UI shows that stage and the backend reruns all rules on the normalized Markdown.
4. The UI shows chunk and vector counts separately. A staged vector is not described as searchable.
5. The backend reports `searchable` only after the production chunk promotion transaction commits.
6. The documents list refreshes after successful promotion. Subsequent chat requests query the new vectors through the existing role-filtered SQL search, and citations open the authorized passage.
7. A document classified `public` is visible to all four roles; `internal` to internal, restricted, and admin; `restricted` to restricted and admin. Classification and `allowed_roles` are computed and enforced by the backend. The browser cannot widen access.
8. On failure, the job reports a safe diagnostic and the database contains no partially searchable document. Staging rows for the job are removed.

## Record model

The existing `documents` row becomes the durable corpus record. Existing columns remain compatible; new columns are added by an idempotent schema migration.

### Corpus document fields

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID/string primary key | Stable identity used by chunks, listings, chat citations, and jobs. |
| `schema_version` | integer | Version of the persisted corpus-record shape. |
| `origin` | enum: `checked_in`, `admin_upload` | Keeps checked-in seed items distinct from runtime additions. |
| `manifest_path` | nullable string | Relative checked-in corpus path; null for frontend uploads. |
| `title` | string | User-facing title; required and non-empty. |
| `classification` | enum: `public`, `internal`, `restricted` | The access tier selected by an admin. Missing or invalid values fail closed. |
| `markdown_content` | text | Normalized source content retained for viewing and re-embedding. Never returned to a user without the document access check. |
| `content_sha256` | 64-character hex string | Idempotency and content-integrity key over normalized Markdown. |
| `content_bytes` | integer | Size of the uploaded bytes, checked against the 4 MB cap. |
| `media_type` | string | Validated type derived from both extension and content-type policy. |
| `source_urls` | JSON array of URLs | Provenance for non-synthetic content. |
| `retrieved_at` | nullable ISO date | Date external source material was retrieved. |
| `reuse_basis` | text | Why content may be used; required for checked-in or runtime non-synthetic items. |
| `synthetic` | boolean | Marks demo-authored internal/restricted material. |
| `synthetic_label` | nullable string | Must equal `SYNTHETIC: for demonstration only` when synthetic. |
| `parser_version` | string | Version of extraction, normalization, and record mapping behavior. |
| `ruleset_version` | string | Version of the canonical regex and metadata validation rules. |
| `embedding_version` | string | Provider/model/dimension version used to create the stored vectors. |
| `embedding_dimension` | integer | Must match the pgvector column and runtime embedding configuration. |
| `sync_state` | enum: `pending`, `validating`, `embedding`, `staging`, `promoting`, `searchable`, `failed` | Durable state surfaced in the documents UI. |
| `chunk_count` | integer | Total chunks expected for this record. |
| `vectors_written` | integer | Number of vectors currently written to staging for this job. |
| `uploaded_by` | user ID | Admin audit attribution; checked-in records may be null. |
| `created_at`, `updated_at`, `searchable_at` | timestamps | Lifecycle and audit times. `searchable_at` is assigned only after commit. |

### Ingestion job fields

Add a `corpus_ingestion_jobs` table so progress survives page refreshes and each event can be associated with one upload.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID primary key | Job ID sent in the first progress event. |
| `document_id` | nullable foreign key | Set after a valid corpus record is prepared. |
| `admin_id` | foreign key | Actor who started the job. |
| `filename` | string | Display-only submitted filename; never used as a storage path. |
| `status` | enum: `running`, `succeeded`, `failed` | Overall job result. |
| `stage` | enum | Current stage from the pipeline below. |
| `sequence` | integer | Monotonic event number for ordered client updates. |
| `progress` | JSON object | Counts, timings, and safe stage messages. |
| `diagnostics` | JSON array | Rule codes, severity, and line number; never matched text. |
| `error_code` | nullable string | Stable failure category safe for display. |
| `created_at`, `started_at`, `finished_at`, `updated_at` | timestamps | Job lifecycle and timing. |

### Chunk/vector fields

Continue using the existing `chunks` and `staging_chunks` tables. Each chunk keeps `document_id`, text, heading path, content hash, embedding, and server-computed `allowed_roles`. Add `embedding_version` if required to prevent vectors from different models being mixed. `allowed_roles` is derived only from document classification.

## Canonical parser and regex rules

Create one pure Python parsing/validation module under `backend/corpus/`. It owns the corpus record shape, file extraction contract, normalization, regex definitions, and safe diagnostics.

- `backend/corpus/validate.py` calls the shared parser for checked-in manifest items instead of maintaining separate copies of sensitive-data and structural rules.
- Manifest validation retains manifest-only checks in addition to calling the shared parser: safe relative paths, every Markdown file listed exactly once, required provenance keys, and the fixed 11 public / 8 internal / 6 restricted counts. Runtime records never change those counts.
- `backend/services/ingestion.py` calls the same shared parser for frontend uploads; it does not reimplement corpus regexes.
- The frontend performs only convenience checks (required fields and file size/type hint). The backend response is authoritative and contains the rule ID, readable message, and optional line number, but no matched secret or raw sensitive value.
- The canonical rule set covers UTF-8 and null bytes, supported extension/content type, 4 MB size limit, title/classification/provenance, first non-empty H1, control characters, unsafe script content, long base64 runs, Aadhaar, PAN, AWS-style access key, email, and Indian phone patterns.
- If the first pass fails, normalization converts extracted text to Markdown, normalizes Unicode to NFC, removes disallowed control characters, repairs heading structure, supplies admin metadata, and masks recognized sensitive matches. Every rule is rerun. Any remaining failure prevents document promotion.
- Regex diagnostics use stable rule codes and line numbers. They do not store matched values, context snippets, or raw API credentials.

The parser accepts a typed metadata object and bytes/text, and returns a typed `ParsedCorpusRecord` containing normalized Markdown, validated metadata, hashes, versions, and a `ValidationReport`. It has no database, HTTP, or React dependencies, which lets the offline validator and runtime endpoint use the same behavior.

## Ingestion and live synchronization

Keep the current stages visible and add precise vector-write accounting:

1. `upload` — extension, content type, and 4 MB check.
2. `parse` — decode/extract and create the typed candidate record.
3. `regex_validate` — run the canonical rules; show rule-level result counts.
4. `normalize` — only when needed.
5. `recheck` — require every blocking rule to pass.
6. `chunk` — create deterministic Markdown chunks with headings and content hashes.
7. `embed` — call the configured NVIDIA free embedding model in batches, recording `embedded/total`.
8. `stage_vectors` — write batches to `staging_chunks`, recording `vectors_written/total`; these are not yet returned by search.
9. `promote` — in one database transaction, move all staged rows into `chunks`, update the document record, and set the job successful.
10. `searchable` — emit only after the transaction commit; refresh the documents list and let the next chat retrieval query find the record.

Use one `StreamingResponse` with server-sent progress events for the active upload and a job-status endpoint as the reload/reconnect fallback. Vercel's Python runtime supports streaming responses, and the request remains bounded by the upload cap and configured function duration. The job row is committed independently from chunk promotion so progress and safe failures remain visible if the data transaction rolls back.

Each event has `job_id`, monotonic `sequence`, `stage`, `status`, `message`, optional `completed`/`total`, optional `timing_ms`, and safe diagnostics. The frontend ignores duplicate/out-of-order sequence numbers and closes the stream on a terminal job state. No client-side regex copy is introduced.

## API and UI surface

- Reuse the admin-only ingestion capability and route through a single ingestion service. The route accepts file plus title, classification, provenance fields, and synthetic metadata.
- Add an admin-only `GET` status endpoint scoped to the requesting admin's job. It returns the persisted snapshot and safe diagnostics.
- Keep document listing role-filtered. A newly promoted document appears in the list for roles allowed by its classification.
- Update `IngestionPanel` to display parser diagnostics and per-stage progress, including `embedded/total`, `vectors_written/total`, `promoted`, and the final searchable timestamp.
- Update the API client to parse SSE events and to recover the latest job snapshot if the stream reconnects or the page reloads.
- Chat continues to use the existing permission-filtered pgvector SQL. It can retrieve the new item after commit without a separate cache invalidation step because PostgreSQL is the source of truth.

## Failure and consistency rules

- Invalid metadata, failed parsing, or a failing re-check produces a failed job and no production document/chunk rows.
- Embedding/provider failure removes staging rows and does not mark the record searchable.
- Failure during promotion rolls back promotion, leaves no partially visible chunks, and records a safe job failure.
- A document is searchable only when its production chunk count equals the expected count and the promotion commit has completed.
- Duplicate normalized content with the same classification is idempotent: return the existing searchable document or an active job rather than duplicate chunks. Same content at a different classification requires an explicit admin decision and is not silently merged.
- The SQL role filter remains mandatory for every chat retrieval. `public` users cannot learn that a higher-classification document exists from chat results or citations.
- No real personal or production-sensitive content is sent to hosted embeddings. The demo's internal/restricted materials remain synthetic.

## Acceptance checks

1. Unit tests call the same parser from checked-in corpus validation and runtime upload handling and assert identical normalized output and diagnostic codes for equivalent Markdown/metadata.
2. Test each regex rule with pass/fail fixtures. Verify diagnostics never include the matched value.
3. Test direct-pass, normalize-and-pass, and normalize-still-fails paths. A failed path leaves no document or chunk rows.
4. Test SSE ordering and persistence: upload through `searchable`, monotonic sequence, stage timings, chunk counts, safe failure, and status endpoint authorization.
5. Test `vectors_written` rises as staging batches commit; no staged vector appears in retrieval before promotion; all chunks appear after promotion.
6. In an integration test against disposable PostgreSQL with pgvector, ingest a synthetic OWASP Top 10 sample as `public`; after the terminal event, a public chat retrieval returns a citation from it. Ingest another item as `restricted`; public receives no result/citation while restricted and admin can retrieve it.
7. Verify the frontend supports Markdown, PDF, and DOCX, shows parser findings and live vector counts, refreshes the document list at completion, and reports failure without claiming searchable.
8. Run backend unit/integration tests, the checked-in corpus validator, frontend type-check/build, and an end-to-end admin upload/chat role test.

## Out of scope for this slice

- Appending runtime uploads to or rewriting `backend/corpus/manifest.json`.
- A separate message broker or always-on worker service.
- Duplicate regex implementations in TypeScript.
- Changing the four-role ladder, hybrid search, external document connectors, or LLM provider.
- Presenting a staged vector as searchable before promotion commits.

## Risks and decisions

- **Streaming and runtime duration:** Vercel Python functions support streaming, but a slow embedding-provider response can still reach the configured function duration. Batch size and upload cap must be verified against the deployed plan; failures remain visible through the persisted job status.
- **Migration:** production columns and enum/check constraints need an idempotent migration path. Existing document and chunk rows must remain readable until the migration and re-embedding complete.
- **Parser compatibility:** fixing divergent validator/ingester behavior may change which existing corpus files pass. Run the current corpus validator and tests before flipping runtime routes to the shared parser.
- **Embedding privacy:** hosted preview receives each chunk and query. Keep only synthetic internal/restricted content in the demo and avoid real sensitive uploads.
- **Threshold:** `0.45` remains provisional; this feature's role-checked OWASP acceptance test is a retrieval check, not a complete threshold benchmark.

## References

- Project acceptance specification: `Sentinel Knowledge Base Project Specification and Corpus Plan.md`, sections 2, 3, 4.1–4.2, 5.2–5.3, and 7.
- Vercel Python runtime streaming support: https://vercel.com/docs/functions/runtimes/python
- Vercel streaming functions overview: https://vercel.com/docs/functions/streaming-functions
