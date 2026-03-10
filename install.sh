#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# StockValuation.io installer
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/stockvaluation-io/stockvaluation_io/main/install.sh | bash
# ==============================================================================

APP_NAME="StockValuation.io"
REPO_ARCHIVE_URL="https://github.com/stockvaluation-io/stockvaluation_io/archive/refs/heads/main.tar.gz"
DEFAULT_INSTALL_DIR="${HOME}/stockvaluation-io"
TAVILY_DASHBOARD_URL="https://app.tavily.com/home"
CURRENCYBEACON_SIGNUP_URL="https://currencybeacon.com/register"
CURRENCYBEACON_LOGIN_URL="https://currencybeacon.com/login"
DOCKER_WINDOWS_URL="https://docs.docker.com/desktop/setup/install/windows-install/"
DOCKER_LINUX_URL="https://docs.docker.com/engine/install/"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

TMP_PATHS=()
PROMPT_SOURCE=""
PROJECT_DIR=""
ENV_FILE=""
DOCKER_CMD=("docker")
COMPOSE_CMD=()
DOCKER_PERMISSION_NOTE=""
DOWNLOADER=""
IS_WSL=0
OS=""

cleanup() {
  local path
  for path in "${TMP_PATHS[@]:-}"; do
    rm -rf "$path" 2>/dev/null || true
  done
}
trap cleanup EXIT

track_tmp() {
  TMP_PATHS+=("$1")
}

ui_line() {
  printf "%b%s%b\n" "$BLUE" "============================================================" "$NC"
}

ui_banner() {
  ui_line
  printf "%b%s%b\n" "$GREEN" "   ${APP_NAME} Local Installer" "$NC"
  ui_line
  echo
}

ui_step() {
  printf "%b%s%b\n" "$YELLOW" "=> $1" "$NC"
}

ui_info() {
  printf "%b%s%b\n" "$BLUE" "$1" "$NC"
}

ui_success() {
  printf "%b%s%b\n" "$GREEN" "$1" "$NC"
}

ui_warn() {
  printf "%b%s%b\n" "$YELLOW" "$1" "$NC"
}

ui_error() {
  printf "%b%s%b\n" "$RED" "$1" "$NC" >&2
}

init_prompt_source() {
  if [[ "${NO_PROMPT:-0}" == "1" ]]; then
    PROMPT_SOURCE=""
    return
  fi

  if [[ -n "${SV_INSTALL_PROMPT_FILE:-}" ]]; then
    if [[ ! -r "${SV_INSTALL_PROMPT_FILE}" ]]; then
      ui_error "Cannot read SV_INSTALL_PROMPT_FILE=${SV_INSTALL_PROMPT_FILE}"
      exit 1
    fi
    exec 9<"${SV_INSTALL_PROMPT_FILE}"
    PROMPT_SOURCE="/dev/fd/9"
    return
  fi

  if [[ -r /dev/tty ]]; then
    PROMPT_SOURCE="/dev/tty"
  fi
}

has_prompt_source() {
  [[ -n "${PROMPT_SOURCE}" ]]
}

read_line_prompt() {
  local prompt="$1"
  local default_value="${2:-}"
  local reply=""

  if ! has_prompt_source; then
    echo "$default_value"
    return
  fi

  if [[ -n "$default_value" ]]; then
    read -r -p "$prompt [$default_value]: " reply < "$PROMPT_SOURCE"
    if [[ -z "$reply" ]]; then
      reply="$default_value"
    fi
  else
    read -r -p "$prompt: " reply < "$PROMPT_SOURCE"
  fi

  echo "$reply"
}

read_secret_prompt() {
  local prompt="$1"
  local reply=""

  if ! has_prompt_source; then
    echo ""
    return
  fi

  read -r -s -p "$prompt: " reply < "$PROMPT_SOURCE"
  printf "\n" >&2
  echo "$reply"
}

confirm() {
  local prompt="$1"
  local default_answer="${2:-y}"
  local suffix="[Y/n]"
  local reply=""
  local normalized=""

  if [[ "$default_answer" == "n" ]]; then
    suffix="[y/N]"
  fi

  if ! has_prompt_source; then
    [[ "$default_answer" == "y" ]]
    return
  fi

  while true; do
    read -r -p "$prompt $suffix " reply < "$PROMPT_SOURCE"
    reply="${reply:-$default_answer}"
    normalized="$(printf '%s' "$reply" | tr '[:upper:]' '[:lower:]')"
    case "$normalized" in
      y|yes) return 0 ;;
      n|no) return 1 ;;
      *) ui_warn "Please answer y or n." ;;
    esac
  done
}

detect_downloader() {
  if command -v curl >/dev/null 2>&1; then
    DOWNLOADER="curl"
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    DOWNLOADER="wget"
    return
  fi
  ui_error "This installer needs curl or wget."
  exit 1
}

download_file() {
  local url="$1"
  local output="$2"

  if [[ -z "$DOWNLOADER" ]]; then
    detect_downloader
  fi

  if [[ "$DOWNLOADER" == "curl" ]]; then
    curl -fsSL --proto '=https' --tlsv1.2 --retry 3 --retry-delay 1 -o "$output" "$url"
    return
  fi

  wget -q --https-only --secure-protocol=TLSv1_2 -O "$output" "$url"
}

open_url() {
  local url="$1"

  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 &
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
    return 0
  fi

  if [[ "$IS_WSL" -eq 1 ]] && command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "" "$url" >/dev/null 2>&1
    return 0
  fi

  return 1
}

offer_open_url() {
  local label="$1"
  local url="$2"

  if confirm "Open ${label} in your browser now?" "y"; then
    if open_url "$url"; then
      ui_success "Opened ${label}."
    else
      ui_warn "Could not open your browser automatically."
      echo "Open this page manually: $url"
    fi
  else
    echo "Open this page manually when ready: $url"
  fi
}

detect_platform() {
  case "$(uname -s)" in
    Darwin)
      OS="macos"
      ;;
    Linux)
      OS="linux"
      ;;
    *)
      ui_error "Unsupported operating system: $(uname -s)"
      exit 1
      ;;
  esac

  if [[ "$OS" == "linux" ]] && { [[ -n "${WSL_DISTRO_NAME:-}" ]] || grep -qi microsoft /proc/version 2>/dev/null; }; then
    IS_WSL=1
  fi
}

project_root_from_pwd() {
  if [[ -f "./docker-compose.local.yml" && -f "./.env.example" && -f "./scripts/bootstrap_local_secrets.sh" ]]; then
    pwd
  fi
}

project_root_from_script_dir() {
  local source_path="${BASH_SOURCE[0]:-}"
  local script_dir=""

  if [[ -n "$source_path" && -f "$source_path" ]]; then
    script_dir="$(cd "$(dirname "$source_path")" && pwd)"
    if [[ -f "$script_dir/docker-compose.local.yml" && -f "$script_dir/.env.example" ]]; then
      echo "$script_dir"
    fi
  fi
}

download_project_archive() {
  local target_dir="$1"
  local archive_path
  local extract_dir
  local extracted_root

  archive_path="$(mktemp)"
  extract_dir="$(mktemp -d)"
  track_tmp "$archive_path"
  track_tmp "$extract_dir"

  ui_info "Downloading project files..."
  download_file "$REPO_ARCHIVE_URL" "$archive_path"

  mkdir -p "$target_dir"
  tar -xzf "$archive_path" -C "$extract_dir"
  extracted_root="$(find "$extract_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"

  if [[ -z "$extracted_root" ]]; then
    ui_error "Could not unpack the project archive."
    exit 1
  fi

  cp -R "$extracted_root"/. "$target_dir"/
}

prepare_project_dir() {
  local existing_dir=""
  local target_dir="${SV_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"

  if [[ -z "$target_dir" || "$target_dir" == "/" ]]; then
    ui_error "Refusing to install into an unsafe target directory: ${target_dir:-<empty>}"
    exit 1
  fi

  existing_dir="$(project_root_from_pwd || true)"
  if [[ -z "$existing_dir" ]]; then
    existing_dir="$(project_root_from_script_dir || true)"
  fi

  if [[ -n "$existing_dir" ]]; then
    PROJECT_DIR="$existing_dir"
    ui_success "Using project at $PROJECT_DIR"
    return
  fi

  if [[ -f "$target_dir/docker-compose.local.yml" && -f "$target_dir/.env.example" ]]; then
    PROJECT_DIR="$target_dir"
    ui_success "Using existing install at $PROJECT_DIR"
    return
  fi

  if [[ -e "$target_dir" && -n "$(ls -A "$target_dir" 2>/dev/null || true)" ]]; then
    if ! confirm "Install directory $target_dir already exists and is not empty. Replace it?" "n"; then
      ui_error "Please rerun the installer with SV_INSTALL_DIR pointing to an empty directory."
      exit 1
    fi
    rm -rf "$target_dir"
  fi

  download_project_archive "$target_dir"
  PROJECT_DIR="$target_dir"
  ui_success "Downloaded project to $PROJECT_DIR"
}

set_project_files() {
  ENV_FILE="$PROJECT_DIR/.env"
}

read_env_value() {
  local key="$1"

  if [[ ! -f "$ENV_FILE" ]]; then
    echo ""
    return
  fi

  sed -nE "s/^${key}=(.*)$/\1/p" "$ENV_FILE" | tail -n 1
}

env_value_is_set() {
  local value
  value="$(read_env_value "$1")"
  [[ -n "${value//[[:space:]]/}" ]]
}

set_env_value() {
  local key="$1"
  local value="$2"
  local tmp_file

  tmp_file="$(mktemp)"
  track_tmp "$tmp_file"

  if [[ -f "$ENV_FILE" ]]; then
    awk -v key="$key" -v value="$value" '
      BEGIN { updated = 0 }
      $0 ~ ("^" key "=") {
        print key "=" value
        updated = 1
        next
      }
      { print }
      END {
        if (!updated) {
          print key "=" value
        }
      }
    ' "$ENV_FILE" > "$tmp_file"
  else
    printf "%s=%s\n" "$key" "$value" > "$tmp_file"
  fi

  mv "$tmp_file" "$ENV_FILE"
}

ensure_env_file() {
  local env_example="$PROJECT_DIR/.env.example"

  if [[ ! -f "$env_example" ]]; then
    ui_error "Missing $env_example"
    exit 1
  fi

  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$env_example" "$ENV_FILE"
    ui_success "Created $ENV_FILE"
  else
    ui_success "Using existing $ENV_FILE"
  fi
}

bootstrap_local_secrets() {
  local bootstrap_script="$PROJECT_DIR/scripts/bootstrap_local_secrets.sh"

  if [[ ! -f "$bootstrap_script" ]]; then
    ui_error "Missing $bootstrap_script"
    exit 1
  fi

  /bin/bash "$bootstrap_script"
}

seed_env_from_shell() {
  local key_name
  local value

  for key_name in \
    DEFAULT_LLM_PROVIDER \
    ANTHROPIC_API_KEY \
    OPENAI_API_KEY \
    GEMINI_API_KEY \
    GROQ_API_KEY \
    OPENROUTER_API_KEY \
    TAVILY_API_KEY \
    CURRENCY_API_KEY; do
    value="${!key_name:-}"
    if [[ -n "${value//[[:space:]]/}" ]]; then
      set_env_value "$key_name" "$value"
    fi
  done
}

docker_desktop_url_for_macos() {
  case "$(uname -m)" in
    arm64|aarch64)
      echo "https://desktop.docker.com/mac/main/arm64/Docker.dmg"
      ;;
    x86_64|amd64)
      echo "https://desktop.docker.com/mac/main/amd64/Docker.dmg"
      ;;
    *)
      ui_error "Unsupported Mac architecture: $(uname -m)"
      exit 1
      ;;
  esac
}

run_with_sudo() {
  if [[ "$EUID" -eq 0 ]]; then
    "$@"
    return
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    ui_error "This step needs administrator access, but sudo is not available."
    exit 1
  fi

  sudo "$@"
}

install_docker_macos() {
  local dmg_url
  local dmg_path
  local volume_path="/Volumes/Docker"
  local docker_bin_dir="/Applications/Docker.app/Contents/Resources/bin"

  if [[ ! -d "/Applications/Docker.app" ]]; then
    dmg_url="$(docker_desktop_url_for_macos)"
    dmg_path="$(mktemp)"
    track_tmp "$dmg_path"

    ui_info "Downloading Docker Desktop for macOS..."
    download_file "$dmg_url" "$dmg_path"

    run_with_sudo hdiutil attach "$dmg_path" -nobrowse >/dev/null
    run_with_sudo cp -R "$volume_path/Docker.app" /Applications/
    run_with_sudo hdiutil detach "$volume_path" >/dev/null
  fi

  if [[ -d "$docker_bin_dir" ]]; then
    export PATH="$docker_bin_dir:$PATH"
  fi

  open -a Docker >/dev/null 2>&1 || true
  ui_success "Docker Desktop installed. Waiting for Docker to finish starting..."
}

install_docker_linux() {
  local docker_script

  if [[ "$IS_WSL" -eq 1 ]]; then
    ui_warn "Windows + WSL detected."
    ui_warn "For the smoothest setup, install Docker Desktop on Windows and enable WSL integration."
    offer_open_url "Docker Desktop for Windows" "$DOCKER_WINDOWS_URL"
    exit 1
  fi

  docker_script="$(mktemp)"
  track_tmp "$docker_script"

  ui_info "Installing Docker Engine for Linux from Docker's official installer..."
  download_file "https://get.docker.com" "$docker_script"
  chmod +x "$docker_script"
  run_with_sudo sh "$docker_script"

  if command -v systemctl >/dev/null 2>&1; then
    run_with_sudo systemctl enable --now docker >/dev/null 2>&1 || true
  fi

  if [[ -n "${USER:-}" ]] && id -nG "$USER" 2>/dev/null | grep -qw docker; then
    :
  elif [[ -n "${USER:-}" ]]; then
    run_with_sudo usermod -aG docker "$USER" || true
    DOCKER_PERMISSION_NOTE="Linux note: you may need to sign out and sign back in before plain 'docker' works without sudo."
  fi

  ui_success "Docker installed for Linux."
}

install_docker() {
  if ! confirm "Docker is required. Would you like me to install it now?" "y"; then
    ui_error "Docker is required for the local stack."
    if [[ "$IS_WSL" -eq 1 ]]; then
      echo "Install Docker Desktop for Windows: $DOCKER_WINDOWS_URL"
    elif [[ "$OS" == "macos" ]]; then
      echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    else
      echo "Install Docker from $DOCKER_LINUX_URL"
    fi
    exit 1
  fi

  if [[ "$OS" == "macos" ]]; then
    install_docker_macos
    return
  fi

  install_docker_linux
}

wait_for_docker() {
  local max_attempts="${1:-60}"
  local attempt=1

  while (( attempt <= max_attempts )); do
    if "${DOCKER_CMD[@]}" info >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
    attempt=$((attempt + 1))
  done

  return 1
}

resolve_docker_command() {
  if docker info >/dev/null 2>&1; then
    DOCKER_CMD=("docker")
    return 0
  fi

  if [[ "$OS" == "macos" ]] && command -v open >/dev/null 2>&1; then
    open -a Docker >/dev/null 2>&1 || true
    DOCKER_CMD=("docker")
    if wait_for_docker 90; then
      return 0
    fi
  fi

  if [[ "$OS" == "linux" ]] && command -v systemctl >/dev/null 2>&1; then
    run_with_sudo systemctl start docker >/dev/null 2>&1 || true
    if docker info >/dev/null 2>&1; then
      DOCKER_CMD=("docker")
      return 0
    fi
  fi

  if [[ "$OS" == "linux" ]] && run_with_sudo docker info >/dev/null 2>&1; then
    DOCKER_CMD=("sudo" "docker")
    if [[ -z "$DOCKER_PERMISSION_NOTE" ]]; then
      DOCKER_PERMISSION_NOTE="Linux note: Docker is working through sudo for now."
    fi
    return 0
  fi

  return 1
}

resolve_compose_command() {
  if "${DOCKER_CMD[@]}" compose version >/dev/null 2>&1; then
    COMPOSE_CMD=("${DOCKER_CMD[@]}" "compose")
    return 0
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    if [[ "${DOCKER_CMD[0]}" == "sudo" ]]; then
      COMPOSE_CMD=("sudo" "docker-compose")
    else
      COMPOSE_CMD=("docker-compose")
    fi
    return 0
  fi

  return 1
}

ensure_docker_ready() {
  if ! command -v docker >/dev/null 2>&1; then
    install_docker
  fi

  if ! resolve_docker_command; then
    ui_error "Docker is installed, but I could not connect to it."
    if [[ "$OS" == "macos" ]]; then
      echo "Please finish Docker Desktop's first-run setup, then rerun this installer."
    else
      echo "Please start Docker and rerun this installer."
    fi
    exit 1
  fi

  if ! resolve_compose_command; then
    ui_warn "Docker Compose is missing."
    install_docker
    if ! resolve_docker_command || ! resolve_compose_command; then
      ui_error "Docker Compose is still unavailable after installation."
      exit 1
    fi
  fi

  ui_success "Docker is ready."
}

has_any_llm_key() {
  local key_name
  for key_name in ANTHROPIC_API_KEY OPENAI_API_KEY GEMINI_API_KEY GROQ_API_KEY OPENROUTER_API_KEY; do
    if env_value_is_set "$key_name"; then
      return 0
    fi
  done
  return 1
}

prompt_for_llm_provider() {
  local choice

  printf "Supported providers:\n" >&2
  printf "  1) Anthropic Claude\n" >&2
  printf "  2) OpenAI\n" >&2
  printf "  3) Google Gemini\n" >&2
  printf "  4) Groq\n" >&2
  printf "  5) OpenRouter\n" >&2

  while true; do
    choice="$(read_line_prompt "Choose a provider number" "")"
    case "$choice" in
      1) echo "claude|ANTHROPIC_API_KEY|Anthropic Claude" ; return ;;
      2) echo "openai|OPENAI_API_KEY|OpenAI" ; return ;;
      3) echo "gemini|GEMINI_API_KEY|Google Gemini" ; return ;;
      4) echo "groq|GROQ_API_KEY|Groq" ; return ;;
      5) echo "openrouter|OPENROUTER_API_KEY|OpenRouter" ; return ;;
      *) ui_warn "Please choose 1, 2, 3, 4, or 5." ;;
    esac
  done
}

configure_llm_keys() {
  local provider_data
  local provider_name
  local env_key
  local display_name
  local api_key

  if has_any_llm_key; then
    ui_success "At least one LLM key is already configured."
    if ! confirm "Would you like to add or update another LLM key?" "n"; then
      return
    fi
  elif ! has_prompt_source; then
    ui_warn "No LLM key found and no interactive prompt is available. Continuing without AI features."
    return
  elif ! confirm "Would you like to add an LLM key now?" "y"; then
    if ! confirm "Continue without an LLM key? AI analysis and chat will stay unavailable until you add one." "n"; then
      configure_llm_keys
    fi
    return
  fi

  while true; do
    provider_data="$(prompt_for_llm_provider)"
    provider_name="${provider_data%%|*}"
    provider_data="${provider_data#*|}"
    env_key="${provider_data%%|*}"
    display_name="${provider_data#*|}"

    api_key="$(read_secret_prompt "Paste your ${display_name} API key")"
    if [[ -z "$api_key" ]]; then
      ui_warn "No key entered. Nothing was saved."
    else
      set_env_value "$env_key" "$api_key"
      set_env_value "DEFAULT_LLM_PROVIDER" "$provider_name"
      ui_success "Saved ${env_key} and set DEFAULT_LLM_PROVIDER=${provider_name}"
    fi

    if ! confirm "Would you like to add or update another LLM key?" "n"; then
      break
    fi
  done

  if ! has_any_llm_key; then
    if ! confirm "Continue without an LLM key? AI analysis and chat will stay unavailable until you add one." "n"; then
      configure_llm_keys
    fi
  fi
}

configure_tavily_key() {
  local api_key

  if env_value_is_set "TAVILY_API_KEY"; then
    ui_success "TAVILY_API_KEY is already configured."
    return
  fi

  if ! has_prompt_source; then
    ui_warn "No Tavily key found and no interactive prompt is available. Continuing without Tavily."
    return
  fi

  ui_info "Tavily powers live web research in the agent."
  offer_open_url "Tavily" "$TAVILY_DASHBOARD_URL"

  api_key="$(read_secret_prompt "Paste your Tavily API key (leave blank to skip for now)")"
  if [[ -n "$api_key" ]]; then
    set_env_value "TAVILY_API_KEY" "$api_key"
    ui_success "Saved TAVILY_API_KEY"
    return
  fi

  if confirm "Continue without Tavily? Live web-backed research will be limited until you add it." "y"; then
    ui_warn "Skipping Tavily for now."
    return
  fi

  configure_tavily_key
}

configure_currency_key() {
  local api_key

  if env_value_is_set "CURRENCY_API_KEY"; then
    ui_success "CURRENCY_API_KEY is already configured."
    return
  fi

  if ! has_prompt_source; then
    ui_error "CURRENCY_API_KEY is required, and no interactive prompt is available."
    ui_error "Set CURRENCY_API_KEY in your environment or in $ENV_FILE and rerun the installer."
    exit 1
  fi

  ui_info "CurrencyBeacon is required to start the valuation service."
  offer_open_url "CurrencyBeacon sign-up" "$CURRENCYBEACON_SIGNUP_URL"
  echo "If you already have an account, you can sign in here: $CURRENCYBEACON_LOGIN_URL"

  while true; do
    api_key="$(read_secret_prompt "Paste your CurrencyBeacon API key")"
    if [[ -n "$api_key" ]]; then
      set_env_value "CURRENCY_API_KEY" "$api_key"
      ui_success "Saved CURRENCY_API_KEY"
      return
    fi
    ui_warn "CurrencyBeacon is required to finish setup."
  done
}

start_stack() {
  ui_info "This first run can take a few minutes while Docker builds the services."
  (
    cd "$PROJECT_DIR"
    "${COMPOSE_CMD[@]}" -f docker-compose.local.yml up -d --build
  )
}

print_success_summary() {
  echo
  ui_line
  printf "%b%s%b\n" "$GREEN" "   Setup complete" "$NC"
  ui_line
  echo "Project folder: $PROJECT_DIR"
  echo "Frontend:        http://localhost:4200"
  echo "Valuation API:   http://localhost:8081"
  echo "Agent API:       http://localhost:5001"
  echo "Chat API:        http://localhost:5002"
  echo
  echo "To stop everything later:"
  echo "  cd \"$PROJECT_DIR\" && ${COMPOSE_CMD[*]} -f docker-compose.local.yml down"
  echo
  echo "To view live logs:"
  echo "  cd \"$PROJECT_DIR\" && ${COMPOSE_CMD[*]} -f docker-compose.local.yml logs -f"
  if [[ -n "$DOCKER_PERMISSION_NOTE" ]]; then
    echo
    ui_warn "$DOCKER_PERMISSION_NOTE"
  fi
  ui_line
}

main() {
  init_prompt_source
  detect_platform
  ui_banner

  ui_step "Preparing project files"
  prepare_project_dir
  set_project_files

  ui_step "Preparing environment"
  ensure_env_file
  bootstrap_local_secrets
  seed_env_from_shell

  ui_step "Checking Docker"
  ensure_docker_ready

  ui_step "Configuring API keys"
  configure_llm_keys
  configure_tavily_key
  configure_currency_key

  ui_step "Starting the local stack"
  start_stack

  print_success_summary
}

if [[ -z "${BASH_SOURCE[0]:-}" || "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
