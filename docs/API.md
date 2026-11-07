# Shared engine API contract

Base path is /api. The website uses the Vite proxy to localhost:8000 in development. The CLI defaults to http://127.0.0.1:8000 and accepts --url.

## Authentication and control plane

The website signs in through Supabase Auth. Live engine calls carry Authorization: Bearer <Supabase access token>. The engine verifies that token with the configured Supabase Auth user endpoint.

Profiles, organizations, invitations, roles and permission settings are exposed through the existing Supabase RPCs in migrations/. Both clients must use that shared control plane. Target credentials and target execution remain server-owned.

## Live endpoints

| Method and path | Input | Output |
| --- | --- | --- |
| PUT /engine/databases/{uuid}/connection | JSON uri string | status, reflected table count in `tables`, and table/column/type map in `schema` |
| PUT /engine/databases/{uuid}/import | Raw UTF-8 CSV, up to 1 MB | records table, columns and imported row count |
| GET /engine/databases/{uuid}/schema | No body | dialect and permitted tables/columns/types |
| POST /engine/databases/{uuid}/generate | JSON question string | sql, provider, requires_execution, attempts, cache |
| POST /engine/databases/{uuid}/query | JSON sql string | columns, rows, row_count, sql, elapsed_ms |

Connection and import actions require an organization administrator. Query/schema/generation require QUERY_ONLY or SCHEMA_EDIT and explicit database permissions. An admin role alone does not create a data grant.

The connection and import responses contain metadata for the administrator's setup review. They contain no row values and do not create a query grant. Continue to use the separate policy-filtered GET schema endpoint for the query workspace.

Generated SQL must be shown for review before live execution. Execution resolves permissions again. Request the query endpoint explicitly after user confirmation.

Common questions on imported sources can return a local draft with provider `morphy-template`. Examples include `average age by city`, `count records by department`, `bottom 3 by revenue` and `who earns the lowest?`. The engine resolves permitted column names and common synonyms. Numeric operations skip blank or nonnumeric fields. Highest and lowest person queries return ties. This path sends no prompt or rows to the model.

For other imported-source questions, the model receives the typed question and pseudonymized schema hints derived from column names. It receives no row values. Candidate SQL is validated for the SQLite target before being returned or cached.

The permitted CSV schema response includes `question_examples`, a list of starter questions built from permitted column names. Clients may send `include_clarification: true` with a generation request. If a common CSV term matches multiple permitted columns, the response can contain `kind: "clarification"`, a `message`, and `choices` with `column` and `question` fields, instead of a SQL draft. Clients opt in to this response shape. Other clients still receive the explanatory 422. To use a choice, send its question with `require_template: true`. The engine checks the exact column against the current policy and returns a draft for review. If the choice is stale, the request returns 422.

The query response uses parallel columns and rows arrays. Preserve null values. PostgreSQL numeric/date/UUID values pass through FastAPI's JSON encoding. Avoid assuming every cell is a string.

## Limits and behavior

PostgreSQL v1 supports public base tables with built-in scalar types, SELECTs, joins, aggregates, non-recursive CTEs, nested/correlated queries and UNION/INTERSECT/EXCEPT with an approved function list. Each physical source is filtered inside its own scope. Writes, recursive CTEs, locks and specialized table sources are rejected. Queries are bounded to 32 scopes and 12 physical source references.

CSV imports are registered as SQLite sources. Their single table is records and all input columns are TEXT. Invalid replacements leave prior data intact. Empty CSV fields become null. Imports support at most 64 uniquely named columns, 20,000 records and 16 KB per field.

Live results have a 1,000-row cap and a 2 MB content limit. PostgreSQL statements have a ten-second timeout. Generation allows up to three local model attempts. Clients currently allow 195 seconds for generation.

Rows are filtered inside each source before joins and aggregates. Column permissions constrain the visible schema. User restrictions intersect role grants and add conjunctive row predicates.

Redis stores generated SQL for exact questions and current database/schema/policy/model/graph fingerprints. Every cache hit is revalidated. Cached results never grant execution authority.

## Errors

FastAPI errors use a detail field. Handle 401 by asking the user to sign in again, 403 as denied access, 409 as missing/incompatible connection setup, 413 as oversized input/result, 422 as validation/generation failure, 502 as database failure and 503 as service/configuration unavailability.

Display actionable messages without exposing credentials. Do not blindly retry execution. Generation and schema requests may be retried by the user.

## Saved query definitions (Supabase Data API)

Use the signed-in user's Supabase client and the `saved_queries` table. Its REST path is `/rest/v1/saved_queries` on the Supabase origin. The resource stores SQL text only. Sharing makes the full definition, including SQL literals, visible to eligible organization members.

| Operation | Client contract |
| --- | --- |
| Create | Insert `org_id`, `database_id`, `title`, `sql_text`, and optionally `shared`. A client-generated UUID in `id` supports retry reconciliation. Treat duplicate IDs as a conflict and read the existing definition before retrying. |
| List | Select by `org_id` with `updated_at` descending and `id` as a tie-breaker. RLS filters every row by current database access. |
| Edit, share or unshare | Update `title`, `sql_text` or `shared` with filters on both `id` and the last observed `revision`. Request returned rows. An empty result requires a reload because the version or permissions changed. |
| Delete | Delete by `id` and last observed `revision`. Only the author with current query access may delete. |
| Execute | Pass the selected definition's SQL to the existing authenticated engine query endpoint. The engine validates the current caller's policy again. |

Definitions start private at revision 1. QUERY_ONLY and SCHEMA_EDIT users may author definitions. VIEW_ONLY users may read shared definitions, including the title and SQL, and receive no execution grant. Changing a database grant to NONE removes read access immediately. Database, organization and author IDs are immutable. Deleting the corresponding database or membership removes its associated definitions.

## Sample endpoints

GET /sample/schema returns synthetic commerce metadata and curated example titles.
POST /sample/generate accepts only an exact curated title.
POST /sample/ask accepts a freely typed question and calls the local model.
POST /sample/query executes against the synthetic SQLite dataset with a fixed APAC policy.
GET /health reports API availability.

Sample data is independent of organization authorization and must be labeled wherever presented.



## Dashboard panels

POST /engine/dashboards/{dashboard_id}/panels/{query_id}/render executes the visible stored query under the caller’s current data policy. VIEW_ONLY is supported for this saved-panel action. See [DASHBOARDS.md](DASHBOARDS.md) for definition CRUD, visibility and panel ordering.

## Profile editing and invitation withdrawal


Apply migration 005. Call these Supabase RPCs with the signed-in session:


- `update_profile({full_name, avatar})` edits only the caller's existing display name and avatar path. Send the current avatar path to keep it, or null to clear it. Upload WebP to the caller's existing `<user-id>/profile.webp` Storage path first. Clearing the reference does not delete the stored object. Names must contain 1–80 characters after trimming. Global username and account id remain unchanged. Refresh the caller's `profiles` record after success.

- `revoke_invitation({inv})` withdraws a pending invitation for an organization administrator. Revoking an already revoked invite is a no-op. Accepted invitations cannot be revoked; this action never removes a member. Recipient and administrator can read the `revoked` status through the existing invitation policy.

- `invite_person({o, person, r})` can reissue a revoked invite. Reissue creates a new invitation id, preserves the single row per organization/recipient, and records the current inviter, role and timestamp. Clients must refresh invitation ids; an old id cannot accept a reissued invitation. Updating a pending invitation keeps its id.

- `accept_invitation({inv})` requires the matching account and pending status. Acceptance of an already accepted id by its recipient remains idempotent. Acceptance, withdrawal and reissue serialize per organization, so a simultaneous accept/revoke has exactly one winner.


Direct profile and invitation writes remain disallowed. Invitation actions write audit events. Profile editing does not alter database permissions. Frontend and CLI account/settings screens must call these RPCs; no new engine HTTP endpoints are required.



## Optional Parquet import

Install `backend/requirements-parquet.txt` on the engine. PUT a raw file to `/engine/databases/{id}/import` with Content-Type `application/vnd.apache.parquet`. The target must be a registered SQLite import and the caller an organization administrator. Missing dependencies return 503. Invalid files return 422 and leave the previous import intact.

Limits are 1 MB per upload, 20,000 rows, 64 flat columns and 16 MB declared expanded data. Strings, numbers, booleans, dates and timestamps are supported. Nested and binary fields are rejected. Data is normalized into the existing encrypted CSV-backed records table with TEXT fields and the same column-name, field-size and normalized 1 MB limits. Empty strings and nulls become SQL NULL. Query and dashboard permissions use the existing engine checks.
