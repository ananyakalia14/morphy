# Completion status

## Working and tested
- Neo-brutalist web frontend and six-animal animation package.
- Supabase schema, authenticated RPCs, organization ownership, invitations and custom roles.
- Role and user policy intersections, table/column allowlists and equality row predicates.
- PostgreSQL connections and encrypted CSV imports with read-only execution.
- Non-recursive CTEs, nested SELECTs, correlated EXISTS and UNION/INTERSECT/EXCEPT with source-level policy filtering.
- Real local Qwen inference, semantic pseudonyms, AST restoration and bounded correction.
- Offline MiniLM anchors and authorized foreign-key graph expansion.
- SQL/result inspection, session history, activity viewer and live-query CLI.
- Full interactive terminal CLI (morphy & sq) with prompt-toolkit, GoTrue Supabase authentication, OS keyring credential storage, context switching, connection & CSV management, profile editing, invitation revocation, saved queries, and terminal dashboard.
- Combined local startup script, stable encryption key and repeatable migrations.

## Implemented with runtime verification still open
- Full local Supabase account, OAuth and Storage journeys. Docker's Linux engine currently cannot start on this machine.
- Organization UI using live Supabase sessions. Database/API tests use injected identities and real PostgreSQL fixtures.
- Redis exact-question SQL cache. No Redis service is running here.
- Updated combined launcher requires a working Docker engine before its Supabase stage can be exercised.

## Original requirements still requiring implementation
- MySQL, MariaDB, Snowflake, BigQuery, DuckDB, ClickHouse, MongoDB and Parquet connectors.
- Redis HNSW semantic SQL cache, Cuckoo-filter username acceleration and Redis Streams audit worker.
- Web saved/shared queries and dashboards (CLI implementation completed with /save-query, /queries, /run-query, /dashboard).
- Frontier-provider benchmark mode and opt-in egress controls.
- Academic Spider/BIRD dataset evaluation and performance measurements.
- Full-screen production database connection wizard (interactive terminal autocomplete implemented in CLI).
- Web profile editing and invitation revocation (CLI implementation completed with /profile edit and /withdraw).
- Production packaging, deployment, key rotation, operational monitoring and recovery validation.

The supported live PostgreSQL query subset is SELECTs, joins, aggregates, non-recursive CTEs, nested queries and set operations using a limited function set and public base tables. CSV import creates a records table with TEXT fields. The graph retriever uses authorized foreign keys and bounded anchors. Benchmark leaderboard and latency targets remain unmeasured.
