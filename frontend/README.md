# MORPHY website — Lovable handoff

Lovable owns the website and workspace interface in frontend/. Keep this React 19 + TypeScript + Vite app as the starting point.

Run npm ci, npm run dev and npm run build from this directory. Copy .env.example to .env.local for independent Supabase configuration. Public project values are allowed in VITE variables. Backend credentials and encryption keys stay in the server environment.

## Existing features

Landing page, six-animal intro/hero, reduced motion, account forms, username claim, optional avatar conversion/upload, organizations, invitations, membership roles, access-policy editor, live query UI, CSV import, activity view and a synthetic query workspace.

LiveEngine.tsx uses authenticated engine endpoints from ../docs/API.md. QueryWorkbench.tsx exposes the labeled synthetic dataset and local-model questions. These flows have different authorization requirements.

The live dataset overview uses permitted schema metadata to suggest a row count and a bounded preview per table. Selecting a suggestion fills the SQL editor. Execution still requires the user's action and the engine's current permission checks.

## Website checklist

- [ ] Complete live Supabase onboarding verification after Docker is operational.
- [ ] Improve the connection/import wizard around supported PostgreSQL and CSV paths.
- [ ] Polish the policy editor using the separate Lovable Access Studio design study.
- [ ] Add accessible schema navigation, query diagnostics, correction-attempt and cache feedback.
- [ ] Add profile editing and invitation revocation with coordinated server changes.
- [ ] Add saved/shared-query and dashboard UI after their control-plane and API contract is defined.
- [ ] Handle expired sessions, permission changes, empty results and service outages.
- [ ] Validate mobile, keyboard, focus, reduced motion and video fallback.
- [ ] Keep labels clear about synthetic data and supported live connectors.
- [ ] Submit screenshots and the production build result with every visual PR.

Preserve the black, white and cobalt palette, square geometry, hard shadows, Syne and JetBrains Mono. Keep the supplied bull and crocodile artwork. Motion sources and final assets live in ../motion/ and public/motion/.

Use web/<topic> feature branches and pull requests to main. Confirm Lovable's integration can target the existing frontend/ directory before syncing. Backend, CLI and migration changes need cross-component review.

