# Verification — 6 November 2026

## Passed
- TypeScript checking and Vite production build.
- Headless Chrome checks for intro dismissal and session persistence, pose selection and pause, 390px layout without horizontal overflow, reduced-motion fallback and no runtime exceptions.
- Chrome decoded both 1920×1080 MP4 and WebM intros with duration 8 seconds.
- PostgreSQL migration applied cleanly to a fresh PostgreSQL 18 fixture using Supabase-compatible auth and storage schemas.
- SQL role checks passed for cross-organization isolation, duplicate case-insensitive usernames, wrong invitation recipients, idempotent acceptance, blocked viewer escalation and direct writes, ownership transfer and default-deny access.
- Two concurrent HTTP callers through standalone PostgREST produced one winner for a username. HTTP tests passed for organization isolation, invitation ownership, blocked escalation, ownership transfer and role/member access intersection.
- Storage table RLS tests blocked foreign avatar insertion and updates.
- Lovable completed the unpublished Access Studio prototype and reported clean type checking, seven model tests and a 390px viewport check.

## Remaining live checks
Docker Desktop fails while initializing local Unix listeners. The approved targeted repair backed up dockerInference and the Secrets Engine listener, but Docker recreated an inaccessible inference listener on the next start. The local Supabase containers could not run.
Therefore actual Supabase Auth signup/session refresh, Google/GitHub redirects, the Storage upload/conversion round trip, onboarding with two real browser sessions and full fresh-instance startup remain unverified here.
The standalone PostgreSQL/PostgREST tests validate policy behavior, with fixture identities. They do not validate the live Auth or Storage services.

## Review notes
The bull and crocodile are contour traces of the supplied images. The other four poses were generated as a matching family and traced. Midpoints are editable typographic guides. Review their letterforms and transitions as first-cut brand artwork.
The films have white backgrounds and the SVGs have transparent backgrounds. The browser uses video playback with static SVG fallback.


## Phase 2 verification
Six FastAPI query tests passed, covering every curated example, OR predicates, star projection without email, blocked writes and unsafe functions, empty results, unknown questions and an enforced result cap.
Chrome passed the real browser → FastAPI → SQLite → result flow. It checked generated SQL, blocked email selection, an attempted OR-policy bypass, refresh and a 390px viewport. Screenshots are workbench-desktop.png and workbench-mobile.png.
The sample service uses synthetic data and a fixed policy. These checks do not establish Supabase-backed query authorization or an AI benchmark score.

## Live engine v0.3
The TypeScript/Vite build passed after adding the Query engine tab.
The real PostgreSQL integration passed for encrypted credential save, allowed-schema discovery, APAC-only aggregation despite a widening OR expression, forbidden-column rejection, unauthorized user query denial and unauthorized connection modification denial.
The second control-plane migration applied successfully to the isolated test database.
The integration injects verified-user identities at the Supabase dependency boundary. A separate unit test checks the Auth user-verification URL, token forwarding and invalid-token denial. End-to-end live Supabase sign-in and local Ollama inference remain unverified because those services are not configured/running here.
The current engine supports PostgreSQL public base tables, flat SELECTs, joins and aggregates with a limited built-in function set. Other dialects, graph retrieval, schema pseudonymization, self-healing and Redis acceleration remain pending.

## Current generation/import verification
12 backend tests passed with the live PostgreSQL fixture and actual qwen2.5-coder:7b model after implementing CSV import and SQL plan validation.
The free-question browser test passed through real Qwen, restored SQL and governed SQLite execution. The expected paid APAC total was 11,650.
Offline MiniLM loaded from existing weights and selected payments for “How much money was paid?” across a schema with unrelated tables.
Redis cache scoping has a regression test. Actual Redis-server calls remain unverified.
The web production build passed after the latest engine and import UI changes.


## Scoped SELECT engine update
Source-level filtering passed for CTEs shadowing table names, nested SELECTs, correlated EXISTS and UNION/INTERSECT/EXCEPT. Hidden columns, denied set-operation branches, mutating CTEs and recursion were rejected. Pseudonym restoration covers reused and correlated aliases. The live PostgreSQL/Qwen run passed 25 tests. The final unit run passed 25 tests and skipped the service-dependent integration.


## Execution evaluation runner
The backend unit run passed 30 tests with one service-dependent integration skipped. New coverage verifies row multiplicity and ordering, protected dataset paths, BIRD-style fields, unchanged database bytes, result-cap exclusions and model/error outcomes. The real local Qwen smoke evaluation agreed on all three synthetic questions. See docs/evaluation-smoke.json.
