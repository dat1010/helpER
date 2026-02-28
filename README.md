# helpER

![helpER image](https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Ftse3.mm.bing.net%2Fth%2Fid%2FOIP.Tn98YfpQoVcRAdHHftuIGQHaGx%3Fpid%3DApi&f=1&ipt=79ca3cc05898db54f28d0b3845c8c8e53880053990abce8abcb2629ec4fe5f53&ipo=images)

Local automation stack for project workflows:
- `Homepage` dashboard
- `Plane` (self-hosted PM via official setup script)
- `OpenClaw` automation engine (planning + implementation loops)

## What this does

`OpenClaw` polls Plane every minute and runs two flows:
1. Planning flow
- Finds work items in `Planning` with label `needs-plan`
- Posts a generated plan comment
- Moves ticket to `Planned`

2. Implementation flow
- Finds work items in `Implement` with label `ready-for-openclaw`
- Enforces one global active implementation ticket at a time
- Creates feature branch + commit artifact + PR in GitHub
- Posts PR link in Plane and moves ticket to `Review`

## Project Layout

- `docker-compose.yml` - Homepage + OpenClaw services
- `scripts/bootstrap.sh` - setup and lifecycle helper
- `scripts/render-homepage-config.sh` - generates Homepage YAML config from `.env`
- `openclaw/` - Python service with Plane/GitHub API integrations
- `homepage/config/` - generated Homepage config files

## Requirements

- Docker + Docker Compose
- `bash`, `curl`
- Plane API token
- GitHub token with repo write + pull request scopes

## Quick Start

1. Initialize env and generated config:
```bash
./scripts/bootstrap.sh init
```

2. Edit `.env` with your Plane/GitHub values:
- `PLANE_BASE_URL` (`http://host.docker.internal` when OpenClaw runs in Docker)
- `PLANE_API_TOKEN`
- `PLANE_WORKSPACE_SLUG`
- `PLANE_PROJECT_IDS`
- `GITHUB_TOKEN`
- `GITHUB_DEFAULT_REPO` or `PROJECT_REPO_MAP`

3. Start local stack:
```bash
./scripts/bootstrap.sh up
```

4. Open services:
- Homepage: `http://localhost:3000`
- OpenClaw dashboard: `http://localhost:8081`
- Plane: default expected at `http://localhost`

## Plane Setup

This repo uses Plane's official installer for local self-hosting.

Install Plane:
```bash
./scripts/bootstrap.sh plane-install
```

Start/stop Plane:
```bash
./scripts/bootstrap.sh plane-start
./scripts/bootstrap.sh plane-stop
```

Notes:
- If a Plane compose file is found in `.plane-selfhost/`, start/stop uses `docker compose` directly.
- Otherwise it falls back to running Plane's `setup.sh` interactively.

## Bootstrap Commands

```bash
./scripts/bootstrap.sh doctor
./scripts/bootstrap.sh init
./scripts/bootstrap.sh up
./scripts/bootstrap.sh status
./scripts/bootstrap.sh logs
./scripts/bootstrap.sh down
./scripts/bootstrap.sh plane-install
./scripts/bootstrap.sh plane-start
./scripts/bootstrap.sh plane-stop
```

## OpenClaw API

- `GET /health` - service health + config errors
- `GET /metrics` - in-memory counters
- `GET /state` - current active implementation ticket state

## Key Environment Variables

See `.env.example` for full list.

Core:
- `OPENCLAW_POLL_SECONDS=60`
- `OPENCLAW_LOG_LEVEL=INFO`

Plane workflow mapping:
- `PLANE_STATE_PLANNING=Planning`
- `PLANE_STATE_PLANNED=Planned`
- `PLANE_STATE_IMPLEMENT=Implement`
- `PLANE_STATE_REVIEW=Review`
- `PLANE_LABEL_NEEDS_PLAN=needs-plan`
- `PLANE_LABEL_READY_FOR_IMPL=ready-for-openclaw`

Repo mapping:
- `GITHUB_DEFAULT_REPO=owner/repo`
- `PROJECT_REPO_MAP={"plane-project-id":"owner/repo"}`

## Current Limitations

- Plane API response shapes can vary by version; this implementation includes fallbacks but may need endpoint/field adjustments.
- Planning output is template-based (not LLM-generated yet).
- Implementation creates a scaffold artifact commit in the target repo to ensure PR creation; it does not yet apply project-specific code changes.
- Idempotency markers are in-memory only (reset on service restart).

## Troubleshooting

- `no such service: helper-homepage` when using compose:
  - Use compose service names, not container names.
  - Correct: `docker compose restart homepage openclaw`
  - Container-name alternative: `docker restart helper-homepage helper-openclaw`

- Plane link in Homepage not reachable:
  - Plane proxy is exposed on port `80` in this setup.
  - Use `HOMEPAGE_PLANE_URL=http://localhost` in `.env`, then rerender config:
    - `./scripts/render-homepage-config.sh`

- OpenClaw errors connecting to Plane (`localhost:8085` from container):
  - Inside Docker, `localhost` points to the OpenClaw container itself.
  - Use `PLANE_BASE_URL=http://host.docker.internal` for OpenClaw.
  - Rebuild/restart OpenClaw:
    - `docker compose up -d --build openclaw`

- Plane installer failed during local image build (`/home/.../apps/api not found`):
  - This can happen if installer falls back to local build path.
  - Preferred path is using installed Plane compose directly:
    - `./scripts/bootstrap.sh plane-start`
  - Script now detects `.plane-selfhost/plane-app/docker-compose.yaml` automatically.

- No planning comment appears:
  - Ticket must match both trigger conditions:
    - State exactly `Planning`
    - Label exactly `needs-plan`
  - Check OpenClaw logs for scan summaries:
    - `docker compose logs -f openclaw`

- No implementation PR appears:
  - Ticket must match:
    - State exactly `Implement`
    - Label exactly `ready-for-openclaw`
  - `GITHUB_TOKEN` must be valid and repo-scoped correctly.

- Metrics show errors increasing:
  - Review logs:
    - `docker compose logs --tail=250 openclaw`
  - Verify `.env` values for Plane base URL, workspace slug, project IDs, and tokens.

## Session Checkpoint (Today)

- Local stack is running with:
  - Homepage (`http://localhost:3000`)
  - Plane (self-hosted)
  - OpenClaw (`http://localhost:8081`)
- Planning flow validated end-to-end:
  - `Planning + needs-plan` -> plan comment posted -> moved to `Planned`
- Implementation flow validated end-to-end:
  - `Implement + ready-for-openclaw` -> branch/PR created -> PR link posted -> moved to `Review`
- Added scan summary logging in OpenClaw for faster debugging:
  - planning: scanned/matched/posted
  - implementation: scanned/candidates

## Next Phase (LLM Worker)

Current OpenClaw logic is orchestration-first and template-driven.  
Future phase is adding an LLM execution worker so the agent can perform real planning and coding work.

Planned additions:
- LLM planner:
  - Build plan from ticket + repo context instead of static template
- LLM implementer:
  - Clone/mount repo, edit code, run tests, generate commit(s), open PR with real code changes
- Safety and control:
  - Approval gates before write operations
  - Budget/token controls
  - Retry and rollback behavior
- Persistence:
  - Durable ticket processing state (not in-memory only)
