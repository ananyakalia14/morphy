# Dashboard data contract

Apply migration 004 after the saved-query migration. Lovable and Antigravity can use the signed-in Supabase client to manage dashboard definitions and panel references.

## Definitions

`dashboards` contains id, org_id, database_id, author_id, title, shared, revision and updated_at. Insert org_id, database_id and title, plus an optional client-generated id and shared flag. Definitions start private. Authors with current query access may change title/shared or delete the dashboard. Use id plus the last observed revision when editing.

`dashboard_panels` contains dashboard_id, database_id, query_id and position. Its primary key is dashboard_id/query_id. Both references must belong to the same database. Insert with the author’s session. Order panels by position then query_id. Positions may tie, and query_id gives a deterministic tie-breaker. Only the dashboard author with current query access may modify its panels.

A reader needs current VIEW_ONLY, QUERY_ONLY or SCHEMA_EDIT access on the database and visibility of the dashboard. Each panel additionally requires visibility of its underlying saved query. Sharing a dashboard and sharing a query are separate choices. Private queries belonging to another author remain hidden.

## Render a panel

POST `/api/engine/dashboards/{dashboard_id}/panels/{query_id}/render` with the current Supabase bearer token. There is no query body. The engine loads the stored SQL through the caller's row-level security context, checks current database access and executes that statement with the caller's column allowlist and row predicates.

VIEW_ONLY users may render visible saved panels. Arbitrary SQL, schema discovery and generation still require query access. Request-body SQL has no effect on panel rendering.

The response uses the same columns, rows, row_count, sql and elapsed_ms fields as the normal query endpoint. Limits and SQL validation are shared. Results are recomputed on every render. A query that references columns outside the viewer's current permissions fails validation.

Missing, private or unshared panels return 404. Removed database access returns 403 or hides the panel before execution. In-flight requests use the permissions resolved for that request.

Dashboard storage and result rendering are ready for client integration. Chart configuration, layout editing, refresh controls and frontend presentation remain client work.
