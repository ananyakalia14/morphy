# MORPHY contributor instructions

Read README.md, docs/API.md and COMPLETION.md before implementing changes.

Codex owns engine integration, migrations and cross-component review. Antigravity primarily edits cli/. Lovable primarily edits frontend/. Changes outside an assigned area must be identified in the PR and coordinated through the shared API contract.

Use main as the integration branch. Work on feature branches named engine/<topic>, cli/<topic> or web/<topic>. Never force-push main. Preserve existing functionality and disclose compatibility changes.

Supabase is the shared identity/control plane. The CLI and website are thin engine clients. Every live query must use the current user's Supabase bearer token. The backend owns target credentials, permission decisions, SQL validation, row filters, inference and execution.

Keep secrets out of commits, logs and screenshots. Preserve .env.example templates. Keep local .env files, .local/, model weights, caches, environments and dependencies ignored.

Describe current behavior truthfully. Synthetic data and curated examples must be labeled. Benchmark, safety and latency claims require measured evidence. Update relevant checklists when behavior changes.

Run the affected checks from CONTRIBUTING.md. Add regression coverage for authorization, policy, data isolation or execution changes. Include UI screenshots for visual changes and note runtime dependencies that were unavailable.

A PR is ready for integration when the implementation works through its normal entry point, the API contract matches the callers, checks pass and actionable review findings are resolved.

