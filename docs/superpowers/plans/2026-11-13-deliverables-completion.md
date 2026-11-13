# Sentinel Knowledge Base Deliverables Completion Plan

> **For agentic workers:** Use the `executing-plans` skill to carry out this plan task by task. Keep each task independently testable and commit it after its checks pass.

**Goal:** Complete the Sentinel Knowledge Base acceptance criteria for authorization, ingestion, retrieval, corpus handling, and Vercel deployment.

**Architecture:** Keep React/Vite as the client, FastAPI as the API, PostgreSQL with pgvector for role-filtered retrieval, and NVIDIA's free hosted endpoints for chat and semantic embeddings. Use the same NVIDIA embedding model and configured 384-dimensional output for ingestion and queries. Use database-backed ingestion state so progress does not depend on a serverless process remaining warm.

**Tech Stack:** React, TypeScript, FastAPI, SQLAlchemy, PostgreSQL, pgvector, Vercel, NVIDIA NIM free preview endpoint by default, optional Groq provider.

**Spec:** `Sentinel Knowledge Base Project Specification and Corpus Plan.md`

## Global Constraints

- The four roles are `public`, `internal`, `restricted`, and `admin`.
- New signups start as `public`; invalid roles deny access; unclassified uploads default to `restricted`.
- Role checks use the database role on every request. Permission filters stay in the SQL vector query, and direct document or chunk access repeats the access check.
- Only admins upload, delete documents, approve users, or change roles.
- Ingestion accepts Markdown, PDF, and DOCX, with a request-size cap below Vercel's 4.5 MB request-body limit; use 4 MB consistently in the browser and API.
- The corpus remains small: 11 sourced public summaries, 8 internal synthetic documents, and 6 restricted synthetic documents. Synthetic documents retain the exact label `SYNTHETIC: for demonstration only` and use no real names or routable IPs.
- Do not use OpenAI services or GPT models, or require any paid model tier. The default chat provider is NVIDIA's currently listed free preview endpoint; Groq is optional only when the selected model is available on the account's free tier. Free endpoint limits and availability must be checked at deployment time.
- Use NVIDIA's free preview embedding endpoint for both passage and query vectors; require `input_type=passage` during indexing and `input_type=query` during retrieval. Re-embed all stored rows when model version or vector dimension changes.
- Keep real personal data and production-sensitive documents out of hosted preview prompts; NVIDIA's hosted trial endpoint may record inputs and outputs under its trial terms. The demo's internal and restricted corpus remains synthetic.
- Do not add connectors, hybrid keyword search, or answer streaming. Ingestion progress events are allowed because the specification requires visible stage progress.
- Every answer retains its own retrieval time, response time, and citations. Follow-up retrieval uses the current question plus recent conversation context.
- Database promotion from staging to production remains atomic. Failed ingestion must not leave a visible document or production chunks.

## Workstream 1: Access control and direct-source access

### Task 1: Align role update API and validate role values

**Files:** `backend/api/routes.py`, `backend/models/schemas.py`, `frontend/src/services/api.ts`, `backend/tests/test_admin_roles.py`

- [ ] Add a role validator that accepts exactly `public`, `internal`, `restricted`, or `admin`.
- [ ] Make the frontend role update use `PATCH /admin/users/{user_id}` with `{ "role": "..." }`, matching the FastAPI route.
- [ ] Add tests asserting invalid role updates return 422 and a valid admin update persists the new role.
- [ ] Run `python -m unittest tests.test_admin_roles -v` from `backend` and `npm.cmd run build --prefix frontend` from the repository root.

### Task 2: Enforce classification on direct document and chunk fetches

**Files:** `backend/api/routes.py`, `backend/models/schemas.py`, `frontend/src/services/api.ts`, `frontend/src/components/chat/ChatConversation.tsx`, `backend/tests/test_document_access.py`

- [ ] Add a shared query predicate for `public -> public/internal/restricted/admin`, `internal -> internal/restricted/admin`, `restricted -> restricted/admin`, and `admin -> all`.
- [ ] Apply it to `GET /documents/{doc_id}`. Return the same 404 response for a missing document and a document outside the caller's clearance.
- [ ] Add `GET /chunks/{chunk_id}` with the same role predicate and a response containing only the authorized source passage, title, and heading path.
- [ ] Make citation controls open the chunk endpoint and render the returned passage. Do not trust citation text sent by the browser.
- [ ] Test all role/document-classification pairs, missing versus unauthorized response equivalence, and an unknown database role returning no records.
- [ ] Run `python -m unittest tests.test_document_access -v` from `backend` and `npm.cmd run build --prefix frontend` from the repository root.

### Task 3: Make approval status an explicit admin action

**Files:** `backend/api/routes.py`, `backend/models/schemas.py`, `frontend/src/components/admin/UserDirectory.tsx`, `frontend/src/services/api.ts`, `backend/tests/test_user_approval.py`

- [ ] Keep registration role `public` and require an explicit approval action before account use if approval is enabled in the product flow.
- [ ] Add an admin-only approval endpoint; reject approval changes from non-admin users.
- [ ] Show approval state and an approve action in the admin user directory.
- [ ] Test a pending account cannot log in, an approved public account can log in, and non-admin approval requests return 403.
- [ ] Run `python -m unittest tests.test_user_approval -v` from `backend` and `npm.cmd run build --prefix frontend` from the repository root.

## Workstream 2: Ingestion gates, safe promotion, and progress

### Task 4: Make each gate match the proposed checks

**Files:** `backend/services/gates.py`, `backend/services/ingestion.py`, `backend/tests/test_gates.py`

- [ ] Validate raw bytes as UTF-8 for Markdown, reject null bytes, and apply extension, content-type, and 4 MB size checks before document parsing.
- [ ] Require a non-empty title and a classification exactly in `public`, `internal`, or `restricted`; keep a missing classification at `restricted`.
- [ ] Require the first non-empty line to match a level-one heading (`# Title`).
- [ ] Add Aadhaar, PAN, AWS-style key, email, and Indian phone patterns to the sensitive-data gate. Do not include matched values in failure messages.
- [ ] Keep the unsafe-script and long-base64 checks, and make each failure identify its gate and reason.
- [ ] Add tests for every gate's pass and fail case, including malformed UTF-8, unsupported MIME/extension, oversized content, non-first H1, and each sensitive-data pattern.
- [ ] Run `python -m unittest tests.test_gates -v` from `backend`.

### Task 5: Make normalization produce valid Markdown and safely reject failures

**Files:** `backend/services/gates.py`, `backend/services/ingestion.py`, `backend/tests/test_normalization.py`

- [ ] Normalize Unicode to NFC, strip disallowed control characters, collapse horizontal whitespace, and preserve paragraph and list boundaries.
- [ ] Convert PDF and DOCX extraction to Markdown headings and paragraphs; normalize heading levels instead of treating all extracted text as plain text.
- [ ] Insert the admin-supplied title and classification metadata when absent, prepend a level-one heading if needed, and mask all G7 matches.
- [ ] Re-run every gate after normalization; return specific reasons and roll back the document, staging rows, and production rows if any gate still fails.
- [ ] Test a DOCX, a text PDF, a passing Markdown upload, a normalized upload, a still-failing upload, and rollback after an embedding error.
- [ ] Run `python -m unittest tests.test_normalization -v` from `backend`.

### Task 6: Persist ingestion progress for the admin UI

**Files:** `backend/models/ingestion_job.py`, `backend/api/routes.py`, `backend/services/ingestion.py`, `frontend/src/components/admin/IngestionPanel.tsx`, `frontend/src/services/api.ts`, `backend/tests/test_ingestion_jobs.py`

- [ ] Add an `ingestion_jobs` table with job ID, admin ID, filename, current stage, stage messages/timings, result document ID, and terminal status.
- [ ] Return a job ID from upload acceptance and add an admin-only status endpoint scoped to that job.
- [ ] Update the UI to poll the status endpoint while processing and show upload, gate, normalize (when needed), re-check, chunk, embed, stage, promote, and searchable states with timings.
- [ ] Persist a failed status and gate reasons. Do not create a searchable document unless promote completes.
- [ ] Test progress transitions, stage timing presence, job ownership, failure reporting, and successful document visibility after promotion.
- [ ] Run `python -m unittest tests.test_ingestion_jobs -v` from `backend` and `npm.cmd run build --prefix frontend` from the repository root.

### Task 7: Enforce the Vercel-safe upload limit end to end

**Files:** `backend/core/config.py`, `backend/api/routes.py`, `frontend/src/components/admin/IngestionPanel.tsx`, `backend/tests/test_upload_limits.py`

- [ ] Set the backend and browser upload maximum to 4 MB, below Vercel's documented 4.5 MB function request-body limit.
- [ ] Read uploads in bounded chunks and stop as soon as the size limit is exceeded; do not read an unbounded request body into memory.
- [ ] Show the same limit in the upload UI and return an actionable 413 response for oversized files.
- [ ] Test a file just below the cap and one just above it.
- [ ] Run `python -m unittest tests.test_upload_limits -v` from `backend` and `npm.cmd run build --prefix frontend` from the repository root.

## Workstream 3: Retrieval, follow-ups, and per-answer citations

### Task 8: Use recent conversation context for follow-up retrieval

**Files:** `backend/models/schemas.py`, `backend/services/retrieval.py`, `backend/tests/test_followup_retrieval.py`

- [ ] Build a retrieval query from the current question and the last few user/assistant turns; cap history by message count and total characters.
- [ ] Use that same contextualized query for embedding and retrieval while preserving the original user question for answer wording.
- [ ] Reject unsupported history roles and ignore any browser-provided system messages.
- [ ] Test a follow-up such as “what about the penalties?” retrieves the same topic's penalty passage when the previous turn identified the topic.
- [ ] Run `python -m unittest tests.test_followup_retrieval -v` from `backend`.

### Task 9: Store timings and citations with each assistant message

**Files:** `frontend/src/pages/Chat.tsx`, `frontend/src/components/chat/ChatConversation.tsx`, `frontend/src/types/index.ts`, `backend/tests/test_chat_response.py`

- [ ] Store each assistant response with its citations, retrieval time, and response time rather than keeping only a single `lastResponse` object.
- [ ] Render each answer's timing fields and numbered source controls beside that answer, including no-answer responses with zero citations.
- [ ] Ensure a no-match answer uses the exact generic response and has no citations.
- [ ] Test serialization of a multi-turn conversation and verify that previous messages keep their own citations and timings after a later answer arrives.
- [ ] Run `python -m unittest tests.test_chat_response -v` from `backend` and `npm.cmd run build --prefix frontend` from the repository root.

### Task 10: Calibrate retrieval for NVIDIA embeddings

**Files:** `backend/core/config.py`, `backend/services/embedding.py`, `backend/services/retrieval.py`, `backend/tests/fixtures/retrieval_questions.json`, `backend/tests/test_retrieval_quality.py`

- [ ] Create a compact question set covering public, internal, and restricted topics, with expected source documents and denied-tier questions.
- [ ] With the NVIDIA free API key configured, measure top-k recall and false-positive behavior using the 384-dimensional Nemotron embedding endpoint and the pgvector SQL query.
- [ ] Set the similarity threshold from those live results; do not reuse a reranker threshold or assume the current `0.75` is calibrated.
- [ ] Keep role filtering, similarity ordering, and `LIMIT` in the same SQL statement.
- [ ] Run `python -m unittest tests.test_retrieval_quality -v` from `backend` and record the measured threshold and limitations in the README.

## Workstream 4: Corpus loading and provenance

### Task 11: Load the checked-in manifest into the database repeatably

**Files:** `backend/corpus/load.py`, `backend/corpus/manifest.json`, `backend/services/ingestion.py`, `backend/tests/test_corpus_load.py`

- [ ] Add an operator-run corpus loader that reads only manifest-listed files and uses the same gates, chunking, embedding, staging, and promotion path as admin uploads.
- [ ] Set each public document's source to its manifest source URL and preserve its reuse basis in document metadata or source display.
- [ ] Mark internal and restricted entries synthetic and preserve their classification.
- [ ] Make repeat runs idempotent by content hash so the loader does not create duplicate documents or chunks.
- [ ] Test counts of 11 public, 8 internal, and 6 restricted documents, repeat-run idempotence, and failure when a public source or synthetic label is missing.
- [ ] Run `python -m unittest tests.test_corpus_load -v` from `backend` and `python -m corpus.validate` from `backend`.

### Task 12: Verify facts and corpus source references

**Files:** `backend/corpus/manifest.json`, `backend/corpus/public/*.md`, `backend/tests/test_corpus_facts.py`

- [ ] Check legal dates and obligations against the linked Gazette, MeitY, PIB, CERT-In, NIST, CISA, and ISO source pages before editing summaries.
- [ ] Keep the DPDP rules notification date tied to the Gazette source, distinguish phased commencement from notification, and avoid stating an unverified breach-reporting timeline.
- [ ] Keep the July 2025 CERT-In audit guideline distinct from the separate 2026 AI security audit material.
- [ ] Check each public source URL, retrieval date, and reuse basis; keep ISO content to the project's own summary and public facts.
- [ ] Run `python -m unittest tests.test_corpus_facts -v` and `python -m corpus.validate` from `backend`.

## Workstream 5: Deployment, provider setup, and acceptance

### Task 13: Configure only free inference endpoints

**Files:** `backend/core/config.py`, `backend/.env.example`, `backend/tests/test_runtime_config.py`, Vercel environment settings

- [ ] Keep NVIDIA NIM as the default provider and set `NVIDIA_API_KEY` in local and Vercel environments; do not restore legacy `CHAT_API_KEY`, `CHAT_API_URL`, or `CHAT_MODEL` variables.
- [ ] If using Groq, set `AI_PROVIDER=groq`, a Groq key, and a model currently available on that account's free tier. Keep `GROQ_CHAT_MODEL` explicit rather than silently selecting a potentially paid model.
- [ ] Verify the selected provider/model is still a free endpoint and confirm its current rate limits immediately before deployment.
- [ ] Test missing-key behavior, provider selection, provider authentication failure, and fallback response without logging secrets.
- [ ] Run `python -m unittest tests.test_runtime_config -v` from `backend`.

### Task 14: Add a single acceptance checklist for all four roles

**Files:** `backend/tests/test_acceptance_matrix.py`, `docs/acceptance-checklist.md`

- [ ] Verify public sees only public content; internal sees public and internal; restricted sees all three classifications; admin can see all and perform admin actions.
- [ ] Verify an unauthorized-tier question returns the generic no-answer text with no citations, and an invalid role receives no documents or chunks.
- [ ] Verify new signup is public, role changes take effect on the next request, document deletion removes chunks immediately, and direct ID fetches re-check authorization.
- [ ] Verify both ingestion paths: normalized input that passes after re-check becomes searchable within seconds, while a persistent gate failure reports reasons and leaves no production rows.
- [ ] Verify follow-up retrieval, per-answer citations and timings, corpus counts/provenance, and admin-only upload/delete/role actions.
- [ ] Run `python -m unittest discover -s tests -v` from `backend`; run `npm.cmd run build --prefix frontend` from the repository root.

### Task 15: Complete README and Vercel deployment verification

**Files:** `README.md`, `vercel.json`, `.python-version`, `backend/requirements.txt`

- [ ] Document architecture, role filtering, deny-by-default, the embedding migration marker, ingestion gates and promotion, corpus provenance, NVIDIA/Groq provider configuration, and the demo's retrieval limits.
- [ ] Document that internal and restricted corpus items are synthetic, the app is not legal advice, the free endpoints have quotas and may change, and no paid OpenAI/GPT provider is used.
- [ ] List current gaps plainly: small corpus, provisional 0.45 threshold calibrated only against five public-corpus queries (not internal or restricted documents), no hybrid search, and no external connectors.
- [ ] Pin a Vercel-supported Python version and exclude Python tests and fixtures from the function bundle with `functions.excludeFiles` in `vercel.json` if the current service configuration supports it.
- [ ] Confirm the production environment contains the NVIDIA free endpoint key and database URL without printing either value.
- [ ] Push to `main`, inspect the Vercel build log for the Python function bundle staying under 500 MB, verify `/health`, then run the role-based acceptance checklist against the deployed app.

## Completion Criteria

- All four roles pass the access matrix, including direct document and citation fetches.
- The ingestion UI reports all stages and timings; normalized success and persistent failure both behave as specified.
- Follow-up questions retrieve using recent context, and every answer has its own timings and authorized citations.
- The corpus loader produces 11 public, 8 internal, and 6 restricted documents with validated provenance and synthetic labels.
- Backend tests and the frontend production build pass; the Vercel deployment stays within the function bundle limit and uses a configured free provider.

## References checked for this plan

- Vercel Python functions, bundle exclusion, and 500 MB standard limit: https://vercel.com/docs/functions/runtimes/python
- Vercel function request-body limit: https://vercel.com/docs/functions/limitations
- NVIDIA free endpoint status for Nemotron 3.5 Bolt E4B: https://build.nvidia.com/nvidia/nemotron-3_5-bolt-e4b
- NVIDIA standalone chat endpoint and required model ID prefix: https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-bolt-e4b-infer
- NVIDIA free Nemotron embedding endpoint, passage/query modes, and 128–2048 output dimensions: https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-embed-1b-infer
- NVIDIA hosted API trial and free prototype access: https://docs.api.nvidia.com/nim/docs/product
- Groq model availability and rate limits: https://console.groq.com/docs/models and https://console.groq.com/docs/rate-limits
