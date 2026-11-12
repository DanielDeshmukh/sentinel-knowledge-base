# Public Landing Page and Account Setup Design

## Status

Design approved in conversation on 2026-11-12. Implementation has not started.

## Goals

- Replace the redirect from `/` to `/chat` for signed-out visitors with a public, branded landing page.
- Explain the real end-user question-answering flow without presenting administrator-only document ingestion as a user workflow.
- Add persistent display names to user accounts and collect a name during public registration.
- Bootstrap four named accounts in local and deployed PostgreSQL without hard-coded passwords or recurring runtime seeding.
- Add an accessible password show/hide control to the existing sign-in and registration form.

## Out of Scope

- Changing retrieval ranking, role policy, answer generation, or citation behavior.
- Requiring email verification or changing the existing public-registration approval policy.
- Storing future registrants' passwords or other per-user credentials in Vercel environment variables.
- Running the production migration or creating production accounts as part of implementation.
- Reworking administrator-only ingestion.

## Approved Product Direction

The public page uses the existing graphite-and-sage theme and reuses the established chat-message and source-card visual language. The response example is explicitly illustrative; it does not claim to show a live request, actual latency, or real corpus documents. Motion is limited to brief entrance transitions and must respect `prefers-reduced-motion`.

The visual query panel is accompanied by a concise explanation of the user-facing path. It must not include the administrator-only upload, validation, chunking, embedding, staging, or promotion pipeline.

## User Query Flow and Copy Constraints

The current backend flow is:

1. An authenticated user submits a question to `POST /chat`.
2. The user's role is applied to chunk retrieval through `allowed_roles` before results are used. Retrieval is vector-similarity based and results below the configured similarity threshold are discarded.
3. If relevant chunks are found, the response generator uses those passages, the question, and up to six recent conversation messages as context.
4. The response includes source metadata and excerpts for the retrieved chunks.
5. If no qualifying chunks are found, the backend returns a no-relevant-authorized-documents response. If the language-model request fails, the current fallback returns retrieved passage text with an availability note.

Landing-page wording must describe these behaviors accurately. It may say that responses are grounded in retrieved authorized passages and that source excerpts are shown. It must not imply that every question will have an answer, that retrieved content is exhaustive, or that the page displays a live query trace.

## Routes and Authentication UX

- `/` is public and renders the landing page for signed-out visitors.
- While authentication state is loading, the route must wait for that state before rendering or redirecting, avoiding a signed-in landing-page flash.
- Authenticated visitors to `/` are redirected to `/chat`.
- The existing combined `/login` screen remains the sign-in and registration surface.
- The landing page's sign-in action opens `/login`; its account-creation action opens `/login?mode=register`.
- Switching between sign-in and registration remains available on the auth screen.
- Registration collects a required display name, email, and password. Sign-in remains email plus password.
- New registrations continue to be public-role and auto-approved, matching current behavior.

## User Data and API

Add a required `display_name` string to the persisted `User` model and the user API response. Registration input requires `display_name`; login input does not. Registration stores the display name along with the submitted email and password hash. Email remains the login identifier.

Update the frontend user and registration types, API call, auth context, and user directory so the display name is retained and shown alongside the email. Preserve the existing password hashing and token flow.

### Existing Database Migration

The current database initializer uses SQLAlchemy table creation and does not by itself add a column to already-existing PostgreSQL tables. Provide an explicit, repeatable schema-upgrade step for the new column:

1. Add `display_name` to new `users` tables.
2. Add the column to existing `users` tables if absent.
3. Backfill existing rows from the email local-part by replacing common separators with spaces and title-casing the result.
4. Enforce `NOT NULL` only after every existing row has a value.

The upgrade must be safe to run on both local and deployed databases. It must not rewrite unrelated user fields.

## Initial Accounts and PostgreSQL Bootstrap

Create these four initial accounts:

| Display name | Login email | Role |
|---|---|---|
| Tommy Vercetti | `tommy.vercetti@example.com` | `admin` |
| Ken Rosenberg | `ken.rosenberg@example.com` | `public` |
| Lance Vance | `lance.vance@example.com` | `public` |
| Sonny Forelli | `sonny.forelli@example.com` | `public` |

`example.com` is a reserved example domain. These addresses are login identifiers for the sample accounts, not actual mailboxes; the application currently has no email verification.

Use an explicit one-time backend command, run separately with the local and deployed PostgreSQL `DATABASE_URL`. It must:

- Require separate operator-supplied password environment variables for the four initial accounts when those accounts need to be created or converted.
- Hash passwords with the existing authentication helper; never store or print plaintext passwords.
- Convert an existing `admin@sentinel.local` seed row to Tommy's email and display name, preserve its user ID, and set its password from the Tommy bootstrap input.
- Create the three public accounts and any missing initial account transactionally.
- Be idempotent: a rerun must not reset passwords for already-initialized accounts.
- Abort without partial writes if a target email is occupied by an unrelated account or a conflicting account state is found.
- Leave all other user rows unchanged.

Remove the hard-coded default-admin credential from normal database initialization. Database initialization creates/upgrades schema; it does not seed users at application startup.

The one-time command's environment variables are only for bootstrapping these four initial accounts. They are supplied to the operator-run command when pointing at each database and are not required in Vercel's application runtime. All future users continue to register through the frontend; their password hashes are stored in PostgreSQL.

## Password Visibility

The existing login and registration form shares one password input across both modes. Add a show/hide button using `react-icons` eye and eye-off icons. It must:

- Toggle only the input's `type` between `password` and `text`.
- Use `type="button"` so it cannot submit the form.
- Expose a mode-appropriate accessible label and pressed state.
- Preserve the current validation and submission behavior.
- Work in both sign-in and registration modes.

Add `react-icons` as a frontend dependency and update the package lockfile using the package manager.

## Visual and Accessibility Requirements

- Reuse the app's current dark graphite surfaces, restrained sage accents, DM Sans, and IBM Plex Mono.
- Keep borders soft and use the existing chat message and source-card patterns.
- Do not add a glowing AI dashboard aesthetic, looping scan animation, fabricated online status, or placeholder performance metrics.
- Keep landing actions and auth controls keyboard accessible with visible focus states.
- Ensure layouts work on narrow screens without horizontal overflow.
- Disable entrance transitions under `prefers-reduced-motion: reduce`.

## Error Handling and Security

- Surface registration and seeding errors explicitly; do not report success when a bootstrap email collision or missing password input prevents initialization.
- The seed command must not print credentials, include them in logs, or write them to source-controlled files.
- The app must not contain a hard-coded default admin password.
- Keep the standard login error behavior and registration error feedback.

## Verification

1. **Schema and API:** Verify the migration on both a fresh schema and an existing schema with users; verify name backfill and `NOT NULL`. Verify registration accepts and persists a display name, `GET /auth/me` returns it, and login remains email/password based.
2. **Bootstrap command:** With an isolated test PostgreSQL database, verify the existing development admin is renamed without changing its ID, all four roles and password hashes are correct, unrelated users remain unchanged, collisions abort transactionally, and reruns do not reset passwords.
3. **Frontend:** Build the frontend. Verify `/` renders for signed-out users, signed-in users are redirected to `/chat`, the account CTA opens registration mode, registration submits the display name, and sign-in still works.
4. **Password control:** Verify the eye control toggles visibility in both auth modes, does not submit the form, and is keyboard accessible.
5. **Content and responsive UI:** Verify the landing copy follows the user query path above, contains no admin upload pipeline, and has no horizontal overflow on mobile. Check reduced-motion behavior.

Production migration and account creation require the operator to run the documented commands with the intended production database URL and securely supplied initial passwords; implementation validation must not connect to production.
