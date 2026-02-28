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
- `PLANE_BASE_URL`
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
- Plane: default expected at `http://localhost:8085`

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
