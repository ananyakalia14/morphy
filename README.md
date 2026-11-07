# MORPHY

A governed natural-language database workspace with a FastAPI engine, a React website and a Python CLI.

This repository is the shared source of truth for Codex, Antigravity and Lovable. The engine verifies Supabase sessions, loads effective database policies, validates SQL, and executes read-only requests. The current implementation supports PostgreSQL and encrypted CSV imports queried through SQLite.

## Who builds what

| Contributor | Primary area | Integration responsibility |
| --- | --- | --- |
| Codex | backend/, migrations/, engine tests | API contract, authorization, SQL policy enforcement and PR review |
| Antigravity | cli/ | Interactive terminal, commands, account flow and engine HTTP client |
| Lovable | frontend/ | Website, onboarding, organization settings and query workspace |
| Project owner | Product decisions and service access | Repository permissions, local services and release decisions |

Work on separate branches and submit pull requests into main. API or migration changes require coordinated updates. Follow [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

## Hosted workspace

The [MORPHY website](https://morphy-web.vercel.app) and [engine health endpoint](https://morphy-engine.vercel.app/api/health) are deployed on Vercel. The website forwards its own `/api` requests to the engine, and both clients use the same hosted Supabase project. CLI users can select the deployed engine with `--url https://morphy-engine.vercel.app`.

Production currently supports governed SQL over the configured sources. The optional Parquet reader, Redis and a remote inference provider must be configured separately. The local Ollama model remains available for development and benchmarking.

## Start locally

Requirements are Node 22, Python 3.12, Docker Desktop with a working Linux engine and Ollama with qwen2.5-coder:7b.

On Windows run ./start-local.ps1 from this repository. It starts local Supabase, applies the control-plane migrations, generates a persistent local encryption key, installs the engine and CLI, and launches the API and web app. Configuration and keys are kept in ignored .local/ files. Stop existing processes on 5173 and 8000 first.

For the standalone sample workspace run ./start-sample.ps1 and open http://127.0.0.1:5173/#explore. Its own-question option uses the local Qwen model and synthetic commerce data.

For an independently configured live engine, copy backend/.env.example to backend/.env.local, fill in its values locally and run ./start-engine.ps1. Configure the website from frontend/.env.example and run npm ci followed by npm run dev in frontend/.

## Current capabilities

- Global usernames, avatars, organizations, invitations, transferable ownership, custom roles and policy configuration.
- Encrypted PostgreSQL credentials and CSV content, authorized schema discovery, read-only queries and bounded results.
- Local Qwen inference, semantic identifier pseudonyms, AST restoration, authorized foreign-key bridges and up to three correction attempts.
- Offline MiniLM anchor retrieval when the optional dependencies and cached model are installed.
- Optional Redis exact-question SQL cache, scoped to database, schema, permissions, model and graph.
- Animated website, SQL/result inspection, session history, organization activity and initial live CLI.

Hosted Supabase password sessions, separate organizations, shared dashboards and permission revocation were verified with two disposable accounts. Email confirmation, OAuth and avatar Storage still need end-to-end checks. Read [COMPLETION.md](COMPLETION.md) and [VERIFICATION.md](VERIFICATION.md) for the exact limits.

## Integration guides

- [Engine API contract](docs/API.md)
- [Execution evaluation guide](docs/EVALUATION.md)
- [Dashboard data contract](docs/DASHBOARDS.md)
- [Antigravity CLI brief and checklist](cli/README.md)
- [Lovable website brief and checklist](frontend/README.md)
- [Repository workflow](CONTRIBUTING.md)
- [Project checklist](COMPLETION.md)

## Checks

Website build runs npm ci and npm run build in frontend/.
Engine checks run python -m pip install -r backend/requirements.txt pytest followed by python -m pytest tests -q in backend/.
Install the terminal with python -m pip install -e ./cli and run morphy --help.

The PostgreSQL integration test requires MORPHY_INTEGRATION_DSN pointing to a disposable migrated control plane. Set MORPHY_TEST_OLLAMA=1 to include real Qwen generation. It creates and removes a separate test database. Browser tests in tests/ require a running website/API and Chrome. Live inference testing additionally requires Ollama.

## Repository layout

backend/ owns the engine and its tests. frontend/ owns the web app. cli/ owns the terminal. migrations/ owns the control-plane schema. motion/ owns original artwork and rendering scripts. The website serves rendered assets from frontend/public/motion/.

Project source is private by default. Choose a license before public distribution.

