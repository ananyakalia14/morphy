# Shared engine API contract

Base path is /api. The website uses the Vite proxy to localhost:8000 in development. The CLI defaults to http://127.0.0.1:8000 and accepts --url.

## Authentication and control plane

The website signs in through Supabase Auth. Live engine calls carry Authorization: Bearer <Supabase access token>. The engine verifies that token with the configured Supabase Auth user endpoint.

Profiles, organizations, invitations, roles and permission settings are exposed through the existing Supabase RPCs in migrations/. Both clients must use that shared control plane. Target credentials and target execution remain server-owned.

## Live endpoints

| Method and path | Input | Output |
| --- | --- | --- |
| PUT /engine/databases/{uuid}/connection | JSON uri string | status and reflected table count |
| PUT /engine/databases/{uuid}/import | Raw UTF-8 CSV, up to 1 MB | records table, columns and imported row count |
| GET /engine/databases/{uuid}/schema | No body | dialect and permitted tables/columns/types |
| POST /engine/databases/{uuid}/generate | JSON question string | sql, provider, requires_execution, attempts, cache |
| POST /engine/databases/{uuid}/query | JSON sql string | columns, rows, row_count, sql, elapsed_ms |

Connection and import actions require an organization administrator. Query/schema/generation require QUERY_ONLY or SCHEMA_EDIT and explicit database permissions. An admin role alone does not create a data grant.

Generated SQL must be shown for review before live execution. Execution resolves permissions again. Request the query endpoint explicitly after user confirmation.

The query response uses parallel columns and rows arrays. Preserve null values. PostgreSQL numeric/date/UUID values pass through FastAPI's JSON encoding. Avoid assuming every cell is a string.

## Limits and behavior

PostgreSQL v1 supports public base tables with built-in scalar types, flat SELECTs, joins and aggregates with an approved function list. CTEs, nested queries, sets, writes and unsafe functions are rejected.

CSV imports are registered as SQLite sources. Their single table is records and all input columns are TEXT. Invalid replacements leave prior data intact. Empty CSV fields become null. Imports support at most 64 uniquely named columns, 20,000 records and 16 KB per field.

Live results have a 1,000-row cap and a 2 MB content limit. PostgreSQL statements have a ten-second timeout. Generation allows up to three local model attempts. Clients currently allow 195 seconds for generation.

Rows are filtered inside each source before joins and aggregates. Column permissions constrain the visible schema. User restrictions intersect role grants and add conjunctive row predicates.

Redis stores generated SQL for exact questions and current database/schema/policy/model/graph fingerprints. Every cache hit is revalidated. Cached results never grant execution authority.

## Errors

FastAPI errors use a detail field. Handle 401 by asking the user to sign in again, 403 as denied access, 409 as missing/incompatible connection setup, 413 as oversized input/result, 422 as validation/generation failure, 502 as database failure and 503 as service/configuration unavailability.

Display actionable messages without exposing credentials. Do not blindly retry execution. Generation and schema requests may be retried by the user.

## Sample endpoints

GET /sample/schema returns synthetic commerce metadata and curated example titles.
POST /sample/generate accepts only an exact curated title.
POST /sample/ask accepts a freely typed question and calls the local model.
POST /sample/query executes against the synthetic SQLite dataset with a fixed APAC policy.
GET /health reports API availability.

Sample data is independent of organization authorization and must be labeled wherever presented.

