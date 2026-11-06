# Working together

## Branches and pull requests

Start from the latest main and create a feature branch in the same repository.

Antigravity uses cli/<topic>. Lovable uses web/<topic>. Codex uses engine/<topic> for engine work and integration fixes.

Submit a pull request into main with a concrete description, checks run and remaining limitations. Use .github/pull_request_template.md. Keep each PR focused on one usable change. Coordinate API changes in docs/API.md and update both callers before merging.

The review checks behavior, permissions, compatibility, error handling and tests. Codex may merge passing PRs under the owner's authorization after actionable findings are resolved. PRs requiring product decisions or service access should explain the needed decision.

Send the PR URL in this chat when it is ready for Codex review. This chat does not have a standing background PR monitor.

## Lovable connection

Connect this GitHub repository to the Lovable project using Lovable's GitHub integration. Confirm that its repository root supports the existing frontend/ app before enabling sync. Work with the existing React/Vite frontend and preserve the backend, CLI and migration folders.

If Lovable syncs directly to a branch, use its supported branching workflow and open a PR into main. Keep main protected against unreviewed direct changes. The separate Access Studio prototype uses sample data. Port its useful UI changes through a PR rather than treating its browser-local policy state as production permissions.

## Checks before merging

All PRs should pass the website build and backend unit tests in the repository-checks workflow.

Frontend changes additionally need desktop/mobile checks, keyboard navigation, reduced motion, service-unavailable behavior and screenshots.
CLI changes need --help, sample commands, authenticated live requests, expired-token behavior, interruption and cancellation checks.
Engine changes need policy and tenant-isolation tests plus a disposable PostgreSQL integration run when applicable. Changes to model prompts need a real local inference check when Ollama is available.

The GitHub workflow runs unit tests and a production website build. PostgreSQL, Supabase, Redis and Ollama runtime checks require their own configured integration environment. State skipped checks in the PR.

## Repository settings

Configure main to require pull requests, resolved conversations and the website / backend checks once their first workflow run exists. Require an approving review where the account plan and available reviewers support it. Disable force pushes and branch deletion for main.

CODEOWNERS requests review from ananyakalia14. Codex reviews through the connected GitHub account in this chat. GitHub will enforce the account's own review restrictions.

Squash-merge focused changes and delete merged feature branches. Never bypass failed checks solely to merge.

