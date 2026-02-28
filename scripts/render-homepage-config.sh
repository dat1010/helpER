#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
CONFIG_DIR="${ROOT_DIR}/homepage/config"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

PLANE_URL="${HOMEPAGE_PLANE_URL:-http://localhost:8085}"
GITHUB_URL="${HOMEPAGE_GITHUB_URL:-https://github.com}"
OPENCLAW_URL="${HOMEPAGE_OPENCLAW_URL:-http://localhost:8081}"

mkdir -p "${CONFIG_DIR}"

cat > "${CONFIG_DIR}/settings.yaml" <<YAML
title: helpER Dashboard
headerStyle: boxedWidgets
layout:
  Infrastructure:
    style: row
    columns: 3
YAML

cat > "${CONFIG_DIR}/services.yaml" <<YAML
- Infrastructure:
    - Plane:
        href: ${PLANE_URL}
        description: Project management API source
    - GitHub:
        href: ${GITHUB_URL}
        description: Code and pull requests
    - OpenClaw:
        href: ${OPENCLAW_URL}
        description: Automation engine dashboard
YAML

cat > "${CONFIG_DIR}/widgets.yaml" <<'YAML'
- resources:
    cpu: true
    memory: true
    disk: /
- datetime:
    text_size: xl
    format:
      dateStyle: full
      timeStyle: short
YAML

cat > "${CONFIG_DIR}/bookmarks.yaml" <<YAML
- Quick Links:
    - Plane:
        - abbr: PM
          href: ${PLANE_URL}
    - OpenClaw:
        - abbr: OC
          href: ${OPENCLAW_URL}
    - GitHub:
        - abbr: GH
          href: ${GITHUB_URL}
YAML
