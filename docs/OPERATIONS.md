# Platform operations

Apply migration `008_platform_operations.sql` before running this engine against the control plane. The local launcher applies it automatically. Use a disposable environment for the first staff and tenant access checks.

Platform roles are independent of organization roles. An operator provisions them through the private schema using a trusted PostgreSQL session. Replace the sample UUID with an existing Supabase Auth user ID.

```sql
insert into morphy_private.ops_staff(user_id, role)
values ('00000000-0000-4000-8000-000000000000', 'operator');
```

Use `viewer` for read access, `reviewer` for incident creation and resolution, and `operator` for restrictions and restoration. Provision named accounts and enroll each account in MFA. Delete the account's row from `morphy_private.ops_staff` to revoke staff privileges. The next request rechecks the role. An organization admin role never grants operations access.

## Lovable handoff

Use the signed-in user's Supabase access token for `/api/ops`. Call `/me` to discover the staff role. A `401` requires reauthentication. A `403` with `detail.code` equal to `mfa_required` requires an MFA challenge and verification, followed by a request using the refreshed token. Other `403` responses indicate missing permission. Use the existing same-origin `/api` proxy. Operations responses are private and have `Cache-Control: no-store` on success.

Lists return `{"items": [...]}` and accept `limit` from 1 to 100 (default 25) and `offset` (default 0). Dates are ISO 8601 timestamps. IDs are UUIDs except for audit action IDs.

| Route relative to `/api/ops` | Contract |
| --- | --- |
| `GET /me` | `role` is `viewer`, `reviewer` or `operator`. |
| `GET /organizations?search=` | Case-insensitive name search. Rows have `id`, `name`, `created_at`, `account_status`, `members`, `active_members_7d`, `last_activity` and `running_jobs`. Activity counts use recorded audit and engine events. |
| `GET /organizations/{id}/members` | Member `id`, `username`, organization `role` and `account_status`. |
| `GET /organizations/{id}/sources` | Source `id`, `dialect` and `quarantined`. |
| `GET /jobs?org_id=&attention=true` | `id`, `org_id`, `actor_id`, `source_id`, `kind`, `state`, `code`, `model_used`, `prompt_flagged`, `started_at` and `finished_at`. Returns the last 30 days. `attention` limits the list to failed, rejected, flagged or unknown jobs. An unfinished job older than 10 minutes is shown as `unknown`. |
| `GET /signals?org_id=` | 15-minute counts per org, actor and source. Rows contain `org_id`, `actor_id`, `source_id`, `code`, `occurrences` and `last_activity`. |
| `GET /incidents?state=open` | `open`, `closed` or `all`. Each incident includes its `id`, target `kind` and `target_id`, optional `job_id`, `reason`, `opened_by`, `opened_at`, `closed_by`, `closed_at` and `resolution`. |
| `POST /incidents` | Reviewer or operator. Send `kind`, `target_id`, `reason` and optional matching `job_id`. Returns the created incident with `201`. |
| `POST /incidents/{id}/resolve` | Reviewer or operator. Send `{"reason":"Reviewed"}`. Returns the closed incident. A repeat returns `409`. |
| `GET /controls/{kind}/{id}` | Returns active `restriction` with `expires_at`, or `null`, plus paginated audit `items` containing action, actor, reason and time. |
| `PUT /controls/{kind}/{id}` | Operator. Send `reason` and `duration_minutes` (1 to 43,200) for user and org suspensions. For source quarantine send `reason` alone. Returns `expires_at`, null for quarantine. An active restriction returns `409`. |
| `POST /controls/{kind}/{id}/restore` | Operator. Send `reason`. Returns `{"restored":true}`. A repeat returns `409`. |

Target kinds are `user`, `organization` and `source`. The server trims reasons and accepts 1–500 characters. Ask staff to describe the evidence without copying customer data. Require a confirmation in the UI for organization-wide suspensions. Show account status separately from activity. Use the incident queue to review signals. Keep the restriction action separate from opening or closing a case.

## Enforcement and signals

- Restrictions apply to new requests using already-issued sessions. User suspension covers MORPHY tenant APIs and avatar access. Supabase Auth still handles sign-in, and signed download links expire on their original schedule. Organization suspension covers that workspace. Source quarantine blocks engine access and saved query/dashboard use for that source. Requests already running can finish.
- Staff see codes and timestamps for authorized query, generation and file import requests. Ordinary malformed input is recorded as `invalid_file`. A recognizable wrong file type produces `file_type_mismatch`; the rejected file is discarded and any prior successful import stays available until staff explicitly quarantine the source. File signature checks are limited to selected formats. Malware scanning and an isolated file parser still require a separate worker.
- Signals are review hints. Thresholds are five policy-blocked queries, twenty generations reaching the model path, or one file mismatch or possible prompt override in 15 minutes for an actor and source. The prompt override flag uses a short phrase match and can have false positives. SQL policy checks and operator decisions remain independent of the heuristic. The public synthetic demo is outside this tenant activity feed.
- Operational jobs contain IDs, timestamps and fixed codes. There are no uploaded bytes, row values, prompts, SQL, schema names or credentials in those records. Incident notes are internal and stay in PostgreSQL. Set a retention policy before production. The feed only shows 30 days of jobs; older database rows remain until pruned. Preserve jobs linked to incidents when pruning.

## Datadog setup

For an engine host running a Datadog Agent, set `MORPHY_DOGSTATSD_PORT` to its loopback UDP port. Leaving it blank keeps metrics off. The engine sends `morphy.ops.jobs` and `morphy.ops.duration_ms` with fixed `kind`, `state`, and `code` tags. The emitter sends no tenant identifiers or incident notes. Keep automatic capture of application request bodies disabled. A Vercel function would need a separate approved metric transport because the emitter uses a local agent.

Create these monitors in the Datadog account once an approved destination is available. Use test traffic and tune the starting thresholds before paging staff.

| Monitor | Starting condition |
| --- | --- |
| Engine liveness | HTTP synthetic check against the engine `/api/health`, alert on consecutive failures. This check covers the process endpoint. |
| Import failure spike | Sum `morphy.ops.jobs` with `kind:import,state:failed` over 15 minutes. Start at 5 failures. |
| Malformed file spike | Sum `morphy.ops.jobs` with `kind:import,code:invalid_file` over 15 minutes. Start at 5 rejections. Review individual file errors in the dashboard. |
| Model failure spike | Sum `morphy.ops.jobs` with `kind:generation,code:model_unavailable` over 15 minutes. Start at 5 failures. |

PostHog is a later product analytics integration. Use explicit onboarding events and keep replay and autocapture disabled on workspace and operations pages.
