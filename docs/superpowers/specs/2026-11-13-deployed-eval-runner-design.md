# Deployed 100-Question Evaluation Runner

**Status:** Design proposal for user review

## Goal

Run a reproducible 100-question evaluation against the deployed Sentinel Knowledge Base API and produce a detailed, local-only record for every query. The run is sequential, waits 10 seconds after each completed query, and stops when the total run reaches 30 minutes.

## Existing Behavior

- The API provides `POST /api/auth/login` and authenticated `POST /api/chat`.
- Chat responses include citations, `retrieval_time_ms`, and `response_time_ms`.
- `retrieval_time_ms` measures retrieval; `response_time_ms` is the total server-side chat duration. The API does not expose a separate model-call timer.
- Evaluator account credentials are stored in the local, Git-ignored `.evaluator-credentials.local.txt` file.
- The checked-in corpus manifest provides 25 source records across public, internal, and restricted classifications.

## Question Set

Store exactly 100 hand-curated, stable cases in `backend/evaluation/questions.v1.jsonl`, separate from the corpus manifest. Each case includes a unique ID, question, target role, answerability, category, expected manifest paths, allowed citation paths, and concise evidence points.

Use the established distribution:

- 35 answerable cases using public-accessible evidence;
- 20 internal-only answerable cases;
- 15 restricted-only answerable cases;
- 20 restricted-access denial probes, split evenly between public and internal roles;
- 10 unsupported or insufficient-evidence cases.

Cover each of the 25 corpus records at least twice among answerable cases. Questions stay grounded in the corpus and focus on defensive cybersecurity, privacy, and data-protection material. Do not include exploit payloads or operational instructions against real targets.

## Runner and Data Flow

`backend/evaluation/run_eval.py` uses only the Python standard library. It reads the ignored evaluator credentials file, authenticates once per role, and sends cases one at a time to the deployed API. The default base URL is `https://sentinel-knowledge-base.vercel.app`, with a command-line override.

Before the run, the runner checks API reachability and verifies that the required evaluator accounts can log in. It stops before the 100-case loop if a preflight fails. Passwords and bearer tokens remain in memory and are never printed or written to results.

For each query, write one JSONL record and one CSV row containing:

- case ID, question, role, answerability, expected evidence points, and expected citation paths;
- UTC start/end timestamps and monotonic client elapsed time;
- HTTP status and a safe success/failure code;
- answer and returned citations, including document title, heading, chunk/document IDs, and returned citation text;
- server `retrieval_time_ms` and `response_time_ms`;
- `generation_phase_estimate_ms`, calculated as `max(response_time_ms - retrieval_time_ms, 0)` when a generated answer is present, otherwise `null`;
- expected/retrieved citation matches, Hit@5, Recall@5, and MRR@5.

The generation phase is only an estimate: it includes answer-generation setup and provider round-trip overhead. It is not a measurement of internal model reasoning, and the runner does not request or record chain-of-thought.

The run starts a 30-minute monotonic deadline. It pauses 10 seconds after a completed query before starting the next one, bounds each request timeout by the remaining run budget, and preserves completed records if the deadline is reached. The final report states whether all 100 cases completed.

## Outputs and Safety

Write raw JSONL, CSV, and a Markdown summary under `backend/evaluation/results/`. These outputs are Git-ignored. The summary includes completion/error counts, per-role and per-category retrieval/citation metrics, latency median/p95, run timestamps, and limitations. Do not claim automatic factual correctness; expected evidence and citation metrics support evaluator review.

The API run is read-only with respect to the database, but it makes up to 100 live model-backed chat requests and may consume provider quota. It never writes credentials, tokens, database URLs, or provider keys to output. It does not modify or ingest corpus data.

## Validation

1. Unit-test question schema/count/category validation, result serialization/redaction, latency calculations, and deadline/pause behavior without network calls.
2. Verify there are exactly 100 unique case IDs, valid manifest paths, the prescribed role/category distribution, and at least two answerable references per manifest record.
3. Perform the live preflight against the configured deployed URL, then run sequentially with the 10-second pause and 30-minute cap.
4. Verify each completed query has timing and citation/result fields, the output directory is ignored, and no credentials or bearer tokens appear in console output or reports.
