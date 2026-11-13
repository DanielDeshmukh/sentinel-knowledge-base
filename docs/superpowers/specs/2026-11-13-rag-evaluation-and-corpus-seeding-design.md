# Corpus Seeding and Timed RAG Evaluation Design

**Status:** Design proposed; awaiting user review of the written specification.

## Goal

Ingest the checked-in 25-record corpus into an isolated Neon branch through the shared parser, then run a reproducible 100-question retrieval and chat evaluation with exact per-query timestamps and latency measurements.

## Current project facts

- The checked-in manifest contains 25 records: 11 public, 8 internal, and 6 restricted.
- The application uses PostgreSQL with pgvector, the shared backend corpus parser, an NVIDIA embedding endpoint, and NVIDIA/Groq chat providers.
- Embeddings are configured for 384 dimensions; the same embedding model must be used for ingestion and query-time retrieval.
- Existing local configuration has `DATABASE_URL` pointed at a local PostgreSQL service on port 5433. A read-only connection attempt was refused; no database writes occurred.
- `TEST_DATABASE_URL` is not set. The target will be a disposable Neon branch so ingestion and evaluation cannot change the shared production database.

## Corpus seeding

Create an idempotent backend command that reads `backend/corpus/manifest.json`, validates the complete manifest and files with the canonical parser before writing, and sends each record through the existing staged ingestion service. Newly created runtime records retain their `manifest_path` and `origin='checked_in'`; they remain separate from the manifest files and evaluation questions remain separate from ingested corpus records.

The command runs sequentially by default, creates a persisted ingestion job per record, reports progress, and stops on the first failed record unless `--continue-on-error` is explicitly supplied. New records use `origin='checked_in'` and their manifest path; existing records with the same normalized content and classification are reused without rewriting their existing provenance. A complete preflight runs before the first database write. The command requires an existing admin user and does not print usernames, password hashes, connection strings, or API keys.

Only the selected Neon branch is mutated. The command identifies its target by safe database metadata (database name and server version), never logs the connection URL, and requires an explicit confirmation flag for writes. The target must have pgvector and the expected 384-dimensional vector schema.

## Evaluation question set

Store exactly 100 version-controlled question records in JSONL, independent of the corpus manifest. Questions are hand-curated against the corpus, not generated at run time. Each record contains:

- stable `case_id` and question text;
- one or more expected manifest paths and allowed citation paths;
- target role and classification boundary;
- answerability and question category;
- concise expected evidence points, not copied source paragraphs;
- expected no-answer behavior for inaccessible or unsupported content.

The set covers public, internal, and restricted material, cross-document synthesis, direct fact lookup, procedural questions, ambiguous queries, and role-based denial cases. Restricted questions are paired with public/internal roles where the expected result is no restricted citation. Questions will be grounded only in the checked-in corpus and will not introduce legal or security claims absent from it.

The fixed composition is 35 public-accessible answerable cases, 20 internal-only answerable cases, 15 restricted-only answerable cases, 20 restricted-access denial probes (10 asked as public and 10 as internal), and 10 unsupported/insufficient-evidence cases. The 70 answerable cases cover every manifest path at least twice.

The runner resolves each expected manifest path to an ingested document by matching the normalized content hash and classification, then uses the document ID returned by retrieval for hit/citation metrics. It also checks `manifest_path` where the matched record was created from the checked-in corpus; reused runtime records may not have that field.

## Evaluation runner and timing

The runner executes the 100 cases sequentially by default, to keep provider rate use and run ordering predictable. It calls the same production retrieval and chat functions as the application, using the configured NVIDIA or Groq provider. It records, for every query:

- `started_at_utc` and `completed_at_utc` as ISO 8601 UTC timestamps with microsecond precision;
- `elapsed_ms` from `time.perf_counter_ns()` (monotonic duration, not wall-clock subtraction);
- backend `retrieval_time_ms` and `response_time_ms` where returned;
- target role, answerability, expected paths, retrieved/cited paths, citation match, Hit@5, Recall@5, MRR@5, and safe error status;
- provider/model identifiers, embedding model/dimension, top-k, similarity threshold, corpus manifest SHA-256, and code revision.

Secrets and raw database connection strings are excluded. The result bundle includes raw JSONL records, a CSV summary, and a Markdown report with run start/end UTC, elapsed duration calculation, per-role and per-classification metrics, no-answer leakage checks, latency median/p95, and a limitations section. The report does not claim factual answer quality from retrieval metrics alone; human review remains the measure for grounding and completeness unless a separate rubric is approved.

The duration formula is `elapsed_ms = (completed_monotonic_ns - started_monotonic_ns) / 1_000_000`. Wall-clock UTC timestamps are for audit ordering; duration uses the monotonic clock so system clock adjustments do not skew latency.

## Safety and credential handling

- Use a disposable Neon branch selected for this evaluation; do not target the production branch.
- Keep secrets in local `backend/.env` or environment variables. Do not paste them in chat or write them to reports.
- Needed configuration names are `DATABASE_URL`, `AI_PROVIDER`, `NVIDIA_API_KEY`, `NVIDIA_EMBEDDING_API_URL`, `NVIDIA_EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `NVIDIA_CHAT_API_URL`, and `NVIDIA_CHAT_MODEL`. If Groq is selected, also set `GROQ_API_KEY`, `GROQ_CHAT_API_URL`, and `GROQ_CHAT_MODEL`.
- `TEST_DATABASE_URL` is optional and must refer to a separate disposable PostgreSQL/pgvector database for integration tests.
- User passwords cannot be retrieved from password hashes. The evaluation may report role counts but will not export password hashes or private credentials. Test access must use an existing account or an approved password reset flow.

## Outputs

- `backend/corpus/ingest_manifest.py`: preflighted, idempotent corpus seeding command.
- `backend/evaluation/questions.v1.jsonl`: exactly 100 fixed evaluation questions.
- `backend/evaluation/run_eval.py`: timed runner using production parser/retrieval/chat behavior.
- `backend/evaluation/results/`: local run outputs; ignored by Git so result content and database identifiers are not committed accidentally.
- `docs/evaluation-report-template.md`: professional report structure; actual results are written only after the database connection and full run succeed.

## Acceptance criteria

1. All 25 manifest records pass the shared parser before the seeding command performs any write.
2. A dry run prints the record count, classification counts, and content hashes without revealing secrets.
3. A confirmed run on the disposable Neon branch makes each record searchable with the intended classification and 384-dimensional vectors; rerunning creates no duplicate documents/chunks.
4. The JSONL question set contains exactly 100 unique case IDs with valid expected manifest paths, 10 unsupported cases, and 20 restricted-record denial probes.
5. Each result record includes exact UTC start/end timestamps and monotonic elapsed milliseconds, plus expected/retrieved document metrics.
6. The report includes per-role retrieval/citation metrics, latency median and p95, data/model/revision metadata, and clearly distinguishes measured results from human answer-quality review.
7. Backend tests, parser validation, dry-run validation, and frontend/backend builds pass. Live ingestion and evaluation are reported as not run if the disposable database or provider credentials are unavailable.
