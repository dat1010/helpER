#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

usage() {
  cat <<USAGE
Usage: scripts/bootstrap.sh <command>

Commands:
  init           Create .env from .env.example and render homepage config
  doctor         Check local prerequisites
  up             Start homepage and openclaw containers
  down           Stop local compose stack
  status         Show service status
  logs           Tail compose logs
  plane-install  Download and run Plane official setup script (interactive)
  plane-start    Start Plane via setup script if installed
  plane-stop     Stop Plane via setup script if installed
USAGE
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

plane_setup_path() {
  echo "${ROOT_DIR}/.plane-selfhost/setup.sh"
}

plane_compose_path() {
  local candidates=(
    "${ROOT_DIR}/.plane-selfhost/docker-compose.yml"
    "${ROOT_DIR}/.plane-selfhost/docker-compose.yaml"
    "${ROOT_DIR}/.plane-selfhost/plane-app/docker-compose.yml"
    "${ROOT_DIR}/.plane-selfhost/plane-app/docker-compose.yaml"
  )
  local c
  for c in "${candidates[@]}"; do
    if [[ -f "${c}" ]]; then
      echo "${c}"
      return 0
    fi
  done
  return 1
}

cmd_init() {
  if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Created .env from .env.example"
  else
    echo ".env already exists; leaving as-is"
  fi
  scripts/render-homepage-config.sh
  mkdir -p openclaw/state
  touch openclaw/state/.gitkeep
  echo "Homepage config rendered"
}

cmd_doctor() {
  require_cmd docker
  docker compose version >/dev/null
  require_cmd curl
  require_cmd bash
  echo "doctor: OK"
  echo "Tip: gh CLI not required; OpenClaw uses GitHub REST API token."
}

cmd_up() {
  [[ -f .env ]] || cmd_init
  scripts/render-homepage-config.sh
  docker compose up -d --build
  echo "Homepage: http://localhost:3000"
  echo "OpenClaw: http://localhost:8081"
  if [[ -f "$(plane_setup_path)" ]]; then
    echo "Plane setup detected at .plane-selfhost/setup.sh"
    echo "Run: scripts/bootstrap.sh plane-start"
  else
    echo "Plane not installed yet. Run: scripts/bootstrap.sh plane-install"
  fi
}

cmd_down() {
  docker compose down
}

cmd_status() {
  docker compose ps
}

cmd_logs() {
  docker compose logs -f --tail=200
}

cmd_plane_install() {
  require_cmd curl
  mkdir -p .plane-selfhost
  pushd .plane-selfhost >/dev/null
  curl -fsSL -o setup.sh https://github.com/makeplane/plane/releases/latest/download/setup.sh
  chmod +x setup.sh
  echo "Launching Plane installer (interactive)..."
  ./setup.sh
  if plane_compose_path >/dev/null 2>&1; then
    echo "Plane compose file detected. You can run:"
    echo "  ./scripts/bootstrap.sh plane-start"
  else
    echo "No Plane compose file found after installer."
    echo "If installer failed during local image build, rerun install and avoid the build fallback."
  fi
  popd >/dev/null
}

cmd_plane_start() {
  local setup compose_file compose_dir env_file
  setup="$(plane_setup_path)"
  if compose_file="$(plane_compose_path)"; then
    compose_dir="$(dirname "${compose_file}")"
    env_file="${compose_dir}/plane.env"
    if [[ -f "${env_file}" ]]; then
      docker compose --env-file "${env_file}" -f "${compose_file}" up -d
    else
      docker compose -f "${compose_file}" up -d
    fi
    echo "Plane started via ${compose_file}"
    return 0
  fi
  [[ -f "${setup}" ]] || { echo "Plane setup script not found. Run plane-install first."; exit 1; }
  echo "Plane compose file not found; falling back to setup.sh interactive menu."
  pushd .plane-selfhost >/dev/null
  "${setup}"
  popd >/dev/null
}

cmd_plane_stop() {
  local setup compose_file compose_dir env_file
  setup="$(plane_setup_path)"
  if compose_file="$(plane_compose_path)"; then
    compose_dir="$(dirname "${compose_file}")"
    env_file="${compose_dir}/plane.env"
    if [[ -f "${env_file}" ]]; then
      docker compose --env-file "${env_file}" -f "${compose_file}" down
    else
      docker compose -f "${compose_file}" down
    fi
    echo "Plane stopped via ${compose_file}"
    return 0
  fi
  [[ -f "${setup}" ]] || { echo "Plane setup script not found."; exit 1; }
  echo "Plane compose file not found; falling back to setup.sh interactive menu."
  pushd .plane-selfhost >/dev/null
  "${setup}"
  popd >/dev/null
}

main() {
  local cmd="${1:-}"
  case "${cmd}" in
    init) cmd_init ;;
    doctor) cmd_doctor ;;
    up) cmd_up ;;
    down) cmd_down ;;
    status) cmd_status ;;
    logs) cmd_logs ;;
    plane-install) cmd_plane_install ;;
    plane-start) cmd_plane_start ;;
    plane-stop) cmd_plane_stop ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
