#!/usr/bin/env bash
set -euo pipefail

# StockValuation.io agent-native installer shim.
# This script intentionally delegates to the constrained Python CLI. It does
# not run valuations, generate reports, or start UI/chat services.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_URL="${STOCKVALUATION_REPO_URL:-https://github.com/stockvaluation-io/stockvaluation_io.git}"
REPO_REF="${STOCKVALUATION_REF:-main}"

default_install_dir() {
  if [[ -n "${STOCKVALUATION_INSTALL_DIR:-}" ]]; then
    echo "$STOCKVALUATION_INSTALL_DIR"
    return
  fi
  if [[ -n "${XDG_DATA_HOME:-}" ]]; then
    echo "${XDG_DATA_HOME}/stockvaluation_io"
    return
  fi
  echo "${HOME:-$PWD}/.local/share/stockvaluation_io"
}

has_repo_files() {
  [[ -f "${ROOT_DIR}/valuation-agent/valuation_agent.py" && -f "${ROOT_DIR}/docker-compose.local.yml" ]]
}

bootstrap_checkout_if_needed() {
  if has_repo_files; then
    return
  fi
  if [[ "${STOCKVALUATION_BOOTSTRAPPED:-}" == "1" ]]; then
    echo "Could not find StockValuation.io repo files next to install.sh." >&2
    exit 1
  fi
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required for the curl installer bootstrap." >&2
    exit 1
  fi

  local install_dir
  install_dir="$(default_install_dir)"
  if [[ -e "$install_dir" && ! -d "${install_dir}/.git" ]]; then
    echo "Install path exists but is not a git checkout: ${install_dir}" >&2
    echo "Set STOCKVALUATION_INSTALL_DIR to a different path and retry." >&2
    exit 1
  fi
  if [[ ! -d "${install_dir}/.git" ]]; then
    mkdir -p "$(dirname "$install_dir")"
    git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$install_dir"
  else
    echo "Using existing StockValuation.io checkout: ${install_dir}"
  fi

  STOCKVALUATION_BOOTSTRAPPED=1 exec bash "${install_dir}/install.sh" "$@"
}

bootstrap_checkout_if_needed "$@"

find_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "$PYTHON_BIN"
    return
  fi
  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  echo "python3.11 or python3 is required." >&2
  exit 1
}

random_secret() {
  local python_bin
  python_bin="$(find_python)"
  "$python_bin" - <<'PY'
import secrets

print(secrets.token_urlsafe(32))
PY
}

ensure_local_env() {
  local project_dir="${PROJECT_DIR:-$ROOT_DIR}"
  local env_file="${project_dir}/.env"
  local env_example="${project_dir}/.env.example"

  if [[ -f "$env_file" ]]; then
    return
  fi
  if [[ ! -f "$env_example" ]]; then
    echo "Missing .env.example at ${env_example}. Cannot create local .env." >&2
    exit 1
  fi

  local postgres_password
  local default_password
  local python_bin
  postgres_password="$(random_secret)"
  default_password="$(random_secret)"
  python_bin="$(find_python)"

  SV_ENV_EXAMPLE="$env_example" \
    SV_ENV_FILE="$env_file" \
    SV_POSTGRES_PASSWORD="$postgres_password" \
    SV_DEFAULT_PASSWORD="$default_password" \
    "$python_bin" - <<'PY'
import os
from pathlib import Path

source = Path(os.environ["SV_ENV_EXAMPLE"])
target = Path(os.environ["SV_ENV_FILE"])
postgres_password = os.environ["SV_POSTGRES_PASSWORD"]
default_password = os.environ["SV_DEFAULT_PASSWORD"]

lines = []
for line in source.read_text(encoding="utf-8").splitlines():
    if line.startswith("POSTGRES_PASSWORD="):
        line = f"POSTGRES_PASSWORD={postgres_password}"
    elif line.startswith("DEFAULT_PASSWORD="):
        line = f"DEFAULT_PASSWORD={default_password}"
    lines.append(line)

target.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
  echo "Created local .env at ${env_file} with generated local passwords."
}

usage() {
  cat <<'EOF'
Usage: ./install.sh [command]

Docker Desktop or a compatible Docker Engine with Compose is required for service commands.

Commands:
  setup          Install/update skills and MCP config, check env, start services, show status
  install        Install/update StockValuation skills and MCP config (default)
  install-skills Install/update skills only
  install-mcp    Install/update MCP config only
  start          Start the local valuation service plumbing
  status         Show local service status
  stop           Stop the local valuation service plumbing
  check-env      Check required env vars without printing values
  uninstall      Remove installed skills and MCP config
  help           Show this help

Optional:
  CLIENT=codex|claude|all      Agent client target (default: all)
  PROJECT_DIR=/path/to/repo    Project directory for service commands/config
EOF
}

run_sv() {
  local python_bin
  python_bin="$(find_python)"
  PYTHONPATH="$ROOT_DIR/valuation-agent${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" -m valuation_agent.cli "$@"
}

run_sv_project() {
  run_sv --project-dir "${PROJECT_DIR:-$ROOT_DIR}" "$@"
}

main() {
  local command="${1:-install}"
  case "$command" in
    setup)
      run_sv_project install all --client "${CLIENT:-all}"
      ensure_local_env
      run_sv_project check-env
      run_sv_project service start
      run_sv_project service status
      ;;
    install)
      run_sv_project install all --client "${CLIENT:-all}"
      ;;
    install-skills)
      run_sv_project install skills --client "${CLIENT:-all}"
      ;;
    install-mcp)
      run_sv_project install mcp --client "${CLIENT:-all}"
      ;;
    start)
      run_sv_project service start
      ;;
    status)
      run_sv_project service status
      ;;
    stop)
      run_sv_project service stop
      ;;
    check-env)
      run_sv_project check-env
      ;;
    uninstall)
      run_sv_project uninstall --client "${CLIENT:-all}"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      echo "Unknown command: $command" >&2
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
