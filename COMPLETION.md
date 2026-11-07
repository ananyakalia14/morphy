# Completion status

## Working and tested
- Private and organization-shared saved SQL definitions with current database permissions and revision-checked client edits.
- Dashboard definitions, panel references and viewer-policy result rendering.
- Profile-editing and invitation withdrawal/reissue RPCs, including concurrent accept/revoke checks.
- Neo-brutalist web frontend and six-animal animation package.
- Supabase schema, authenticated RPCs, organization ownership, invitations and custom roles.
- Role and user policy intersections, table/column allowlists and equality row predicates.
- PostgreSQL connections, encrypted CSV imports and optional bounded Parquet imports with read-only execution.
- Non-recursive CTEs, nested SELECTs, correlated EXISTS and UNION/INTERSECT/EXCEPT with source-level policy filtering.
- Real local Qwen inference, semantic pseudonyms, AST restoration and bounded correction.
- Local Spider/BIRD-style execution-agreement runner with read-only SQLite and explicit error/exclusion counts.
- Redis exact-question draft cache, tested against Redis in CI for round-trip storage, policy scoping and 24-hour expiration settings.
- Offline MiniLM anchors and authorized foreign-key graph expansion.
- SQL/result inspection, session history, activity viewer and live-query CLI.
- Full interactive terminal CLI (morphy & sq) with prompt-toolkit, GoTrue Supabase authentication, OS keyring credential storage, context switching, connection & CSV management, profile editing, invitation revocation, saved queries, and terminal dashboard.
- Combined local startup script, stable encryption key and repeatable migrations.

## Implemented with runtime verification still open
- Full local Supabase account, OAuth and Storage journeys. Docker's Linux engine currently cannot start on this machine.
- Organization UI using live Supabase sessions. Database/API tests use injected identities and real PostgreSQL fixtures.
- Updated combined launcher requires a working Docker engine before its Supabase stage can be exercised.

## Original requirements still requiring implementation
- MySQL, MariaDB, Snowflake, BigQuery, DuckDB, ClickHouse, MongoDB connectors.
- Redis HNSW semantic SQL cache, Cuckoo-filter username acceleration and Redis Streams audit worker.
- Dashboard layout/chart configuration and viewer-facing website/terminal integration (CLI integration completed with /dashboard).
- Frontier-provider benchmark mode and opt-in egress controls.
- Official Spider/BIRD dataset runs, official scoring and representative performance measurements.
- Full-screen production database connection wizard and interactive terminal autocomplete.
- Website/terminal settings for profile editing and invitation withdrawal/reissue (CLI commands completed with /profile edit and /withdraw).
- Production packaging, deployment, key rotation, operational monitoring and recovery validation.

The supported live PostgreSQL query subset is SELECTs, joins, aggregates, non-recursive CTEs, nested queries and set operations using a limited function set and public base tables. CSV import creates a records table with TEXT fields. The graph retriever uses authorized foreign keys and bounded anchors. Benchmark leaderboard and latency targets remain unmeasured.
