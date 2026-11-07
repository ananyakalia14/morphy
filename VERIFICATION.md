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


## Dashboard panel verification
The local PostgreSQL fixture run passed 31 tests, including saved-panel rendering for a VIEW_ONLY user whose row policy differs from the author’s. Request-supplied SQL was ignored, arbitrary query execution stayed denied, a wrong dashboard ID returned 404 and unsharing the saved query removed panel visibility. The first optional model-inclusive run failed because Ollama was offline; the database/API run passed after separating inference from this integration.


Account lifecycle: migration 005 adds caller-only profile editing and admin invitation withdrawal/reissue. A disposable PostgreSQL test checks invalid avatar ownership, invalid names, caller isolation, unauthorized withdrawal, idempotency, stale invitation ids, wrong-account acceptance and simultaneous acceptance/withdrawal. Supabase Auth/Storage UI verification remains open.


Lovable integration (2026-11-07): ported src/morphy from morphy-web-experience commit f39923195ab3d669dc1849e0bcb5d74f6748d62f into the Vite frontend. Restored browser mounting, stylesheet loading and relative media imports. Fixed hero pause before playback starts, session-scoped intro dismissal and reduced-motion intro skipping. Browser checks pass for mobile width, intro dismissal, hero pause, reduced motion and both video formats. Reproduced all 55 merged CLI tests. Hosted migrations 003–005 were applied and their RLS policies verified. Signed-in hosted web/engine testing remains open. Vercel deployment was rejected with 403 because the connected app lacks access to team ananya27.

Hosted signup testing found a pre-existing on_auth_user_created trigger inserting a nonexistent profiles.full_name column. Migration 006 removes only the matching legacy handle_new_user trigger. The CI fixture reproduces this trigger so fresh migration checks exercise its removal. Real Supabase password authentication now succeeds for two disposable accounts.

Hosted integration follow-up: two disposable accounts signed in through GoTrue. Public Data API calls verified separate organizations, invitations, saved queries and dashboards. The local engine verified their real bearer tokens and applied APAC/EMEA row restrictions. Chrome showed totals 20 and 999 for the respective accounts and removed the result after logout. The merged CLI HTTP client returned the owner result and denied the VIEW_ONLY arbitrary query. Both test accounts, organizations, imported records and local session fixtures were deleted afterwards. Public engine deployment remains blocked by Vercel team access.

Parquet import: six normalization/rejection tests and the PostgreSQL-backed API round trip pass. Full backend run has 38 passes with only the Redis runtime check skipped locally. CI installs the optional reader for both backend and PostgreSQL checks.


Production deployment: Vercel serves the web app at https://morphy-web.vercel.app and the FastAPI engine at https://morphy-engine.vercel.app. The same-origin `/api` rewrite returns a healthy response. Two real hosted Supabase sessions were tested with CSV import, tenant isolation, invitation acceptance and separate dashboard row policies. Chrome showed 20 for the owner and 999 for the viewer. Revoking the viewer grant cleared the result on refresh, and signing out removed workspace results for both accounts. Disposable accounts, organizations and local token fixtures were removed. Engine request without a bearer token returned 401.

Local Qwen synthetic execution smoke run: 3/3 correct. This is not an official Spider/BIRD score. Hosted generation requires a reachable model provider. Optional Parquet and Redis are not configured in the deployed engine.
