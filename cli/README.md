# MORPHY CLI — Antigravity handoff

Antigravity owns the terminal interface, commands and client experience in this folder. The shared engine lives in backend/. Read ../docs/API.md and ../AGENTS.md first.

## Existing implementation

The Python package exposes morphy and sq console commands. Install from the repository root with python -m pip install -e ./cli.

morphy starts the sample REPL. Existing commands are /help, /schema, /examples, /ask <question>, /sql <SELECT> and /exit or /quit. The sample /ask uses curated example titles.

morphy --database <UUID> selects a real organization database and reads MORPHY_ACCESS_TOKEN from the environment. --url selects the engine. --sql runs one query and exits. Live /ask previews SQL and requests confirmation before execution.

The current CLI uses httpx and a simple input loop. Access tokens remain in the process environment. It has no persisted login session, token refresh, organization chooser, connection wizard or command completion yet.

## Build on this foundation

- [x] Add prompt-toolkit for slash completion, history, multiline SQL and interruption handling.
- [ ] Add login/logout/status using the same Supabase Auth project as the website.
- [ ] Store persisted refresh tokens in the OS credential store and support session expiry/refresh.
- [ ] Add organization and database selection, keeping current context visible.
- [ ] Add /connect and CSV import flows using the engine's authenticated endpoints.
- [ ] Add profile, invitation and member-management commands through the shared Supabase RPCs.
- [x] Add readable tables, JSON output, CSV export, null handling and bounded output.
- [x] Show generation stages, correction attempts and cache status without invented percentages.
- [x] Add command cancellation, network-timeout messages and graceful Ctrl+C.
- [x] Add noninteractive flags and stable exit codes for scripts.
- [x] Add command tests and integration tests against a disposable development control plane.
- [x] Document Windows, macOS and Linux installation. Validate both console aliases.

## Installation & Setup

### Requirements
- Python >= 3.11

### Installation
From the repository root:
```bash
python -m pip install -e ./cli
```
Both `morphy` and `sq` console commands are installed.

On Windows, macOS and Linux:
```bash
morphy --help
sq --help
```

## Required boundaries

Keep SQL generation, target connections, encryption keys, policy enforcement and execution in the backend. The CLI sends the current user's bearer token to the configured engine. Verify HTTPS for remote authenticated endpoints.

Use the same API request/response shapes as the web app. Never ask an LLM to decide whether a query is authorized. Never execute model output directly against a target database.

Do not commit tokens, passwords or shell history. Source authentication settings from documented configuration. Support existing --url, --database and --sql callers as the interface evolves.

## First PR

Create cli/interactive-shell from main. Add the terminal framework, /help and completion around the existing HTTP client first. Include --help and interruption checks. Submit a PR with usage examples and testing evidence.

