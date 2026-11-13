# Corpus ingestion acceptance checklist

## Admin submission

- [ ] Admin can add Markdown, PDF, or DOCX files up to 4 MB from the admin interface.
- [ ] Public records require valid source URLs, a retrieval date, and a reuse basis.
- [ ] Internal and restricted records are marked synthetic, have no source URL or retrieval date, include a reuse basis, and use the required synthetic label.
- [ ] The backend shared parser is authoritative; parser diagnostics are displayed without exposing matched sensitive values.
- [ ] The UI shows the parser, embedding, staging, promotion, and final searchable states with counts and timings.
- [ ] Refreshing or losing the SSE connection restores status from the owning admin's persisted job snapshot.

## Storage and access

- [ ] Runtime records remain separate from the checked-in corpus manifest.
- [ ] Staged vectors are not visible to retrieval before promotion commits.
- [ ] Chat can retrieve a committed public record for public, internal, restricted, and admin roles.
- [ ] Chat and direct document access do not reveal restricted records to public or internal roles.
- [ ] Repeated normalized content with the same classification reuses the searchable document and does not create duplicate chunks.
- [ ] Parser/embedding failures leave no retrievable chunks; abandoned stale jobs are reconciled and staging rows are cleaned.

## Environment-dependent verification

- Backend unit tests, corpus validation, Python compilation, and the frontend production build run in the local workspace.
- PostgreSQL/pgvector end-to-end tests run only when `TEST_DATABASE_URL` points to a disposable database with permission to create the `vector` extension and a temporary schema. They are skipped when that variable is absent.
