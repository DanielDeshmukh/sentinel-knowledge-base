# Shared Corpus Parser and Live pgvector Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins add corpus items through the frontend using the same canonical backend parser as the checked-in manifest validator, then show persisted live progress until role-authorized chat retrieval can find committed pgvector chunks.

**Architecture:** A pure Python parser owns the corpus record shape and all regex/metadata checks. Both the offline manifest validator and the upload pipeline call it. A persisted ingestion job records progress while the upload response streams events; vector rows are staged in batches and become searchable only after atomic promotion commits. Existing SQL role filtering remains the access boundary.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy, PostgreSQL, pgvector, NVIDIA NIM embeddings, React 18, TypeScript, Vite, Fetch Streams / Server-Sent Events.

**Spec:** `docs/superpowers/specs/2026-11-13-shared-corpus-parser-and-live-sync-design.md`

## Global Constraints

- Roles are `public`, `internal`, `restricted`, and `admin`; documents classify only as `public`, `internal`, or `restricted`.
- An admin is the only role that uploads corpus items; `allowed_roles` is computed by the backend from document classification.
- The request upload cap is 4 MB for Markdown, PDF, and DOCX.
- Checked-in corpus counts remain 11 public, 8 internal synthetic, and 6 restricted synthetic; runtime database records do not change manifest counts.
- The synthetic label is exactly `SYNTHETIC: for demonstration only`.
- One Python regex/parser implementation is authoritative; do not clone corpus regexes in TypeScript.
- Sensitive-match diagnostics contain rule IDs and line numbers only, never matched values or context snippets.
- A chunk in `staging_chunks` is not searchable. Emit `searchable` only after rows are promoted to `chunks` and the transaction commits.
- Chat must keep the `allowed_roles` predicate inside the pgvector SQL query; citations and document listing repeat role authorization.
- Use the configured free NVIDIA embedding model for query and passage vectors; do not add a paid OpenAI/GPT provider.
- Keep real personal or production-sensitive content out of hosted preview inference; internal/restricted demo documents remain synthetic.

---

## Files and interfaces

- `backend/corpus/parser.py`: pure typed corpus metadata, parser result, shared regex rules, diagnostic generation, normalization, and Markdown validation.
- `backend/corpus/validate.py`: checked-in manifest/path/count checks plus calls to the shared parser.
- `backend/services/gates.py`: compatibility wrapper over shared rules while current callers transition.
- `backend/services/ingestion.py`: file extraction and staged ingestion orchestration; consumes the parser result and emits stage callbacks.
- `backend/models/document.py`: persisted corpus provenance, parser/vector versions, content hash, and sync state.
- `backend/models/corpus_ingestion_job.py`: persisted upload progress, stage counts, diagnostics, and lifecycle.
- `backend/models/chunk.py`: vector version metadata where needed; existing `chunks`/`staging_chunks` and role lists remain.
- `backend/models/schemas.py`: API event/job and document response shapes.
- `backend/init_db.py`: idempotent additive schema migration for document/job metadata.
- `backend/api/routes.py`: admin upload SSE endpoint and admin-scoped job status endpoint.
- `frontend/src/types/index.ts`: typed upload, parser diagnostic, SSE progress event, and job snapshot.
- `frontend/src/services/api.ts`: authenticated upload stream reader and job snapshot fetch.
- `frontend/src/components/admin/IngestionPanel.tsx`: metadata form, parser feedback, and live per-stage/vector counts.
- `frontend/src/pages/Documents.tsx`: refresh role-visible document records after the searchable event.
- Tests live in `backend/tests/test_corpus_parser.py`, `test_corpus.py`, `test_gates.py`, `test_ingestion.py`, `test_corpus_jobs.py`, `test_corpus_routes.py`, and `test_retrieval.py`.

## Shared public Python types

Use these interfaces consistently between tasks:

```python
@dataclass(frozen=True)
class CorpusMetadata:
    title: str
    classification: Literal["public", "internal", "restricted"]  # invalid runtime values still yield diagnostics
    source_urls: tuple[str, ...] = ()
    retrieved_at: date | None = None
    reuse_basis: str | None = None
    synthetic: bool = False
    synthetic_label: str | None = None

@dataclass(frozen=True)
class CorpusDiagnostic:
    code: str
    severity: Literal["error", "warning"]
    message: str
    line: int | None = None

@dataclass(frozen=True)
class ParsedCorpusRecord:
    metadata: CorpusMetadata
    markdown: str
    content_sha256: str
    parser_version: str
    ruleset_version: str
    normalized: bool
    diagnostics: tuple[CorpusDiagnostic, ...]
    final_diagnostics: tuple[CorpusDiagnostic, ...]

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.final_diagnostics)

def parse_corpus_record(
    markdown: str, metadata: CorpusMetadata, *, normalize_on_failure: bool = True
) -> ParsedCorpusRecord: ...
```

`valid` is true only when no diagnostic has severity `error`. `content_sha256` is computed over the final normalized UTF-8 Markdown. The parser never reads files, opens a database, makes HTTP calls, or formats a sensitive match into a diagnostic.

The upload service separately validates raw byte count, extension, MIME allow-list, and UTF-8 decoding before passing extracted text and metadata to `parse_corpus_record`. PDF/DOCX extraction returns Markdown-like text and then follows the same parser path as Markdown.

## Task 1: Add the shared parser and establish its failing tests

**Files:**
- Create `backend/corpus/parser.py`.
- Create `backend/tests/test_corpus_parser.py`.
- Modify `backend/corpus/__init__.py` only if package exports are needed.

**Interfaces:** Implement the types and function above. Keep rule codes stable (`G1_ENCODING`, `G2_TYPE_SIZE`, `G3_METADATA`, `G3_CLASSIFICATION`, `G4_CONTROL`, `G5_HEADING`, `G5_CONTENT`, `G6_UNSAFE`, `G7_AADHAAR`, `G7_PAN`, `G7_AWS_KEY`, `G7_EMAIL`, `G7_PHONE`, `G8_PUBLIC_SOURCE`, `G8_PUBLIC_SOURCE_URL`, `G8_RETRIEVED_AT`, `G8_REUSE_BASIS`, `G8_SYNTHETIC_FLAG`, `G8_SYNTHETIC_SOURCES`, `G8_SYNTHETIC_RETRIEVED_AT`, `G9_SYNTHETIC_LABEL`, `G9_SYNTHETIC_CONTENT_LABEL`).

- [x] **Step 1: Write parser tests first.** Cover valid public provenance; valid synthetic classification/label; invalid classification; missing title and body; single-line title; missing first H1; provenance URL validation; each sensitive regex; unsafe script/base64; NFC normalization; control stripping; sensitive redaction; stable SHA-256; and diagnostics without matched text.
- [x] **Step 2: Run the new test file and observe import/assertion failures.**

Run from `backend`: `..\backend\venv\Scripts\python.exe -m unittest tests.test_corpus_parser -v` when invoked from repository root, or `venv\Scripts\python.exe -m unittest tests.test_corpus_parser -v` from `backend`.

Expected: tests fail because `CorpusMetadata`, `parse_corpus_record`, and the diagnostic types do not exist.

- [x] **Step 3: Implement the pure parser.** Move the existing corpus sensitive patterns and equivalent `services/gates.py` checks into compiled module-level patterns. Validate the first non-empty line as `# `, require body text beyond headings/labels, validate metadata and HTTP(S) source URLs, and enforce public provenance or the exact synthetic label/provenance rules. Do not include matched substrings in messages.
- [x] **Step 4: Add normalization and recheck.** Normalize NFC, remove forbidden control characters, ensure the supplied title produces a first level-one heading where needed, insert the synthetic label when needed, redact recognized sensitive values, then rerun every rule. Keep `normalized=True` only if content or metadata changed. Return errors if any blocking check still fails.
- [x] **Step 5: Run parser tests and verify it against the checked-in corpus.**

Run from `backend`: `venv\Scripts\python.exe -m unittest tests.test_corpus_parser -v`.

Expected: all parser cases pass; no diagnostic includes a fixture secret.

Commit: `feat: add shared corpus record parser`.

## Task 2: Route checked-in validation and upload gates through the shared parser

**Files:**
- Modify `backend/corpus/validate.py`.
- Modify `backend/services/gates.py`.
- Modify `backend/services/ingestion.py`.
- Modify `backend/tests/test_corpus.py`.
- Create `backend/tests/test_gates.py`.

**Interfaces:** `validate_corpus(root, expected_counts=None)` remains the CLI/test entry point. `run_gates(text, metadata)` remains available as a compatibility wrapper but obtains its regex results from `parse_corpus_record`.

- [x] **Step 1: Add parity tests first.** For equivalent Markdown and metadata, assert runtime gates and direct shared-parser calls return the same diagnostic codes/output; the manifest validator maps shared rule codes to its stable path-prefixed CLI diagnostics. Manifest-only checks (safe relative paths, all Markdown files listed exactly once, exact 11/8/6 classification counts) remain separate and runtime records do not enter manifest counts.
- [x] **Step 2: Run focused tests and observe parity failures before refactoring.** The new shared-rule assertions failed against the old validator/gates as expected.
- [x] **Step 3: Refactor `validate.py` to call `parse_corpus_record` for each manifest file.** Keep JSON shape, path traversal protection, synthetic/public provenance rules, and count diagnostics in the manifest validator.
- [x] **Step 4: Refactor `run_gates` and `normalize_text` to call the same parser.** Remove duplicated regex definitions. Preserve the current stage API until the streaming task changes it. The existing ingestion service continues through these compatibility wrappers.
- [x] **Step 5: Run the corpus validator and focused tests.** 28 focused tests pass; `python -m corpus.validate` exits successfully for all checked-in records.

Run from `backend`: `venv\Scripts\python.exe -m unittest tests.test_corpus tests.test_corpus_parser tests.test_ingestion -v`; then `venv\Scripts\python.exe -m corpus.validate`.

Expected: checked-in corpus counts and diagnostics are unchanged except for fixes required by the canonical rules; runtime and manifest parser results agree.

Commit: `refactor: share corpus parser across validator and ingestion`.

## Task 3: Persist complete corpus records and ingestion jobs

**Files:**
- Modify `backend/models/document.py`.
- Modify `backend/models/chunk.py` only if embedding version is needed.
- Create `backend/models/corpus_ingestion_job.py`.
- Modify `backend/models/__init__.py` if models are imported there.
- Modify `backend/models/schemas.py`.
- Modify `backend/init_db.py`.
- Create `backend/tests/test_corpus_jobs.py`.
- Create `backend/tests/test_corpus_schema_upgrade.py`.

**Interfaces:** `Document` gains the design's provenance/content/parser/vector/sync fields. `CorpusIngestionJob` has `id`, `document_id`, `admin_id`, `filename`, `status`, `stage`, `sequence`, `progress`, `diagnostics`, `error_code`, and lifecycle timestamps. Add `CorpusJobStatusResponse` with only those safe fields.

- [x] **Step 1: Write failing model and migration tests.** Verify the full document/job field shapes, safe progress response serialization, and idempotent additive DDL for existing documents and staging vectors.
- [x] **Step 2: Run focused tests and observe failures before model/migration implementation.** Initial run failed because the migration function and corpus job model did not exist.

Run from `backend`: `venv\Scripts\python.exe -m unittest tests.test_corpus_jobs tests.test_corpus_schema_upgrade -v`.

- [x] **Step 3: Add nullable columns and a job table.** Add the safe corpus metadata fields, legacy-compatible defaults, sync-state/origin checks, job status/stage checks, progress JSON, and indexes. Content hash remains indexed but not unique until the upload idempotency transaction is implemented in Task 4.
- [x] **Step 4: Extend `upgrade_corpus_schema(connection)` and call it after `Base.metadata.create_all`.** Use `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS`, an advisory transaction lock, and duplicate-safe constraint creation; no destructive schema operations.
- [x] **Step 5: Run focused tests and commit.** Full suite passes (57 tests; one test requiring disposable PostgreSQL skipped). Frontend production build passes from the primary checkout because the isolated worktree has no local Node dependencies and Task 3 does not modify frontend files.

Expected: fresh and pre-existing PostgreSQL schemas can run initialization twice; the second run performs no destructive changes.

Commit: `feat: persist corpus records and ingestion jobs`.

## Task 4: Stream and persist parser-to-pgvector progress

**Files:**
- Modify `backend/services/ingestion.py`.
- Create `backend/services/corpus_job_store.py`.
- Modify `backend/api/routes.py`.
- Modify `backend/models/schemas.py`.
- Modify `backend/tests/test_ingestion.py`.
- Create/update `backend/tests/test_corpus_routes.py`.
- Modify `backend/tests/test_retrieval.py`.

**Interfaces:**

```python
def process_ingestion(
    db: Session,
    file: UploadFile,
    metadata: CorpusMetadata,
    uploaded_by_id: str,
    job_id: str,
    on_progress: Callable[[dict], None],
) -> dict: ...
```

The existing admin-only upload endpoint becomes a streamed response with `text/event-stream`. Each event contains `job_id`, `sequence`, `stage`, `status`, `message`, optional `completed`, `total`, `timing_ms`, and safe `diagnostics`. `GET /admin/corpus/jobs/{job_id}` is admin-only and returns only the owning admin's job (404 for another admin's job).

- [ ] **Step 1: Write failing tests for progress events, job authorization, terminal states, staging invisibility, and cleanup after embedding/promotion failure.**
- [ ] **Step 2: Run `venv\Scripts\python.exe -m unittest tests.test_ingestion tests.test_corpus_jobs tests.test_corpus_routes tests.test_retrieval -v` and verify failures are caused by the missing stream/job behavior.**
- [ ] **Step 3: Implement the ordered stages:** upload, parse, regex_validate, optional normalize, recheck, chunk, embed, stage_vectors, promote, searchable. Use monotonic sequence IDs and update the job with a separate short DB transaction per event.
- [ ] **Step 4: Batch provider embedding calls at 100 inputs or fewer.** Write staged vectors in batches and persist `vectors_written` after each batch; ensure retrieval queries production `chunks` only. On any failure, rollback production changes, delete staging rows for the job, and persist a safe failed job state.
- [ ] **Step 5: Create SSE streaming without blocking the event loop.** Run the synchronous DB/embedding pipeline in a worker thread; bridge callbacks to the async response with a thread-safe queue. Send a terminal event only after job persistence succeeds. Disable response buffering and send heartbeat comments while waiting.
- [ ] **Step 6: Add the status endpoint.** Require admin auth and filter by both job ID and `admin_id`; return the same public-safe progress shape as stream events.
- [ ] **Step 7: Run focused tests and commit.**

Run from `backend`: `venv\Scripts\python.exe -m unittest tests.test_ingestion tests.test_corpus_jobs tests.test_corpus_routes tests.test_retrieval -v`.

Expected: no staged chunk is retrieved; after successful promotion all expected chunks are returned for permitted roles; all failures leave no production chunk rows.

Commit: `feat: stream corpus validation and vector sync progress`.

## Task 5: Add frontend corpus metadata and live sync display

**Files:**
- Modify `frontend/src/types/index.ts`.
- Modify `frontend/src/services/api.ts`.
- Modify `frontend/src/components/admin/IngestionPanel.tsx`.
- Modify `frontend/src/components/admin/DocumentLibrary.tsx` if it presents document sync status.
- Modify `frontend/src/pages/Documents.tsx` only to refresh the role-filtered list after success.

**Interfaces:** `ingestFile(file, metadata, onEvent, signal?)` submits `FormData`, parses SSE chunks, passes typed `CorpusProgressEvent` values to the callback, and returns the terminal event. `getCorpusJob(jobId)` loads a persisted job snapshot after reconnect/reload.

- [ ] **Step 1: Add the TypeScript event/parser tests only if an existing frontend test runner is present; otherwise isolate the SSE decoder in a pure function and verify it with a temporary development fixture plus `npm.cmd run build --prefix frontend`.**
- [ ] **Step 2: Update frontend types before implementation.** Define the same stage/status literals as the API, diagnostics `{ code, severity, message, line }`, and progress counts; do not define regex patterns in TypeScript.
- [ ] **Step 3: Implement authenticated multipart streaming with `fetch`.** Use `ReadableStream` decoding for blank-line-delimited SSE frames, tolerate chunk boundaries and heartbeat comments, ignore events whose `sequence` is not newer, and surface non-2xx JSON errors without dumping response bodies to console.
- [ ] **Step 4: Update the admin form.** Collect title, classification, source URLs, retrieved date, reuse basis, and synthetic marker. Enforce the 4 MB/type allow-list as client feedback only; display server diagnostics as authoritative.
- [ ] **Step 5: Render live pipeline state.** Show regex pass/fail messages, normalization, embedded/total, vectors-written/total, promotion, and the exact searchable event/time. On stream loss, recover from `getCorpusJob`; on success, invalidate/refetch documents.
- [ ] **Step 6: Build and commit.**

Run from repository root: `npm.cmd run build --prefix frontend`.

Expected: type-check and Vite build pass; UI never labels an item searchable based on client-side progress alone.

Commit: `feat: show live corpus validation and pgvector sync`.

## Task 6: Verify end-to-end ingestion, chat visibility, and roles

**Files:**
- Create `backend/tests/test_corpus_end_to_end.py`.
- Modify `backend/tests/test_retrieval.py` if fixture coverage is needed.
- Modify `docs/acceptance-checklist.md` if present or create it.
- Update the design spec only if measured behavior changes a recorded decision.

- [ ] **Step 1: Write an integration test guarded by `TEST_DATABASE_URL` with a disposable PostgreSQL database and pgvector.** Stub only the external embedding call; use the real parser, ingestion service, models, promotion transaction, and retrieval SQL.
- [ ] **Step 2: Test a public synthetic OWASP Top 10 document.** Stream through `searchable`, then ask a matching question and verify its citation appears for public, internal, restricted, and admin users.
- [ ] **Step 3: Test a restricted synthetic document.** Verify public/internal receive the generic no-answer and no citation; restricted/admin can retrieve it. Verify direct document access obeys the same classification predicate.
- [ ] **Step 4: Test failure and idempotency.** Persistent regex failure leaves no document/chunks; embedding failure cleans staging vectors; same normalized content/classification returns the existing document/job without duplicates.
- [ ] **Step 5: Run corpus and backend checks.**

From `backend`: `venv\Scripts\python.exe -m unittest discover -s tests -v`; `venv\Scripts\python.exe -m corpus.validate`.

From repository root: `npm.cmd run build --prefix frontend`.

Expected: unit suite passes; PostgreSQL integration passes when `TEST_DATABASE_URL` is available, otherwise is explicitly reported as skipped.

Commit: `test: verify role-safe live corpus synchronization`.

## Coverage self-review

- Project spec regex gates, normalization, and second-pass validation: Tasks 1–2.
- Admin frontend upload and complete visual pipeline: Tasks 4–5.
- Same corpus parser across runtime and checked-in content: Tasks 1–2.
- Database staging, pgvector synchronization in seconds, and immediate searchability: Tasks 3–4 and 6.
- Four-tier access and no existence leaks: Task 6; existing SQL filter remains unchanged.
- Markdown, PDF, DOCX, source metadata, and synthetic labels: Tasks 1–2 and 5.
- Follow-up context, citations/timings, Vercel deployment, and unrelated authorization backlog: outside this first vertical slice; keep in the larger deliverables checklist.
