# Sentinel Evaluation Corpus Design

**Status:** Approved in chat on 2026-11-13

## Goal

Create a small, provenance-aware corpus for evaluator demonstrations, aligned with section 6 of the project specification. Corpus files are prepared for manual Markdown ingestion; this work does not write to a database.

## Corpus shape

Create 25 Markdown documents:

- 11 public documents: original, concise summaries covering the DPDP Act and Rules, official DPDP guidance, CERT-In directions and advisories, NIST privacy and cybersecurity frameworks, NIST incident response, CISA playbooks, an original ISO/IEC 27001:2022 overview, and practical security awareness.
- 8 internal documents: synthetic policy, acceptable use, access control, classification and handling, incident response, vendor assessment, DPDP checklist, and logging/time synchronization.
- 6 restricted documents: synthetic incident report, penetration-test findings, risk register, breach-notice drafts, security architecture notes, and DPIA-style assessment.

Public content is newly written, not copied from source documents. Do not reproduce paid standards. Do not provide legal advice. Include a legal or regulatory claim only after checking an accessible official primary source; omit a claim if it cannot be verified.

## File and provenance format

Store Markdown files under `backend/corpus/public/`, `backend/corpus/internal/`, and `backend/corpus/restricted/`. Each file starts with a level-one heading, followed by its content and a short references section. Do not use YAML front matter because the current ingestion gate expects the document to begin with a heading.

Store provenance in `backend/corpus/manifest.json`. Each entry records the relative path, title, classification, source URL(s), retrieval date, reuse basis, and whether the document is synthetic. Public documents must have source and reuse notes. Synthetic documents must be labeled `SYNTHETIC: for demonstration only` in both the document and manifest.

Use fictional identities and organizations only. Any example email or network address must use reserved domains or documentation ranges such as `example.com` and `192.0.2.0/24`.

## Validation and boundaries

Add a local validator that checks the expected count and classification totals, first-line headings, provenance for every public document, synthetic labels, and accidental personal-data patterns. The validator must not print matched content.

The deliverable is corpus files, manifest, and validator only. Do not add a database loader, alter API/database schemas, ingest the corpus, or connect to a production database. Persisting provenance into ingested document records is a separate follow-up because the current upload API does not accept source/license metadata.

## Source verification

Prefer primary government and standards-body sources. NIST SP 800-61 Rev. 3, the NIST Cybersecurity Framework, NIST Privacy Framework, and CISA playbooks are available from their official sites. MeitY, PIB, and CERT-In pages were blocked in the initial fetch attempt; obtain accessible official primary-source material before writing India-specific facts. Record the canonical source URL and retrieval date for each source actually used.
