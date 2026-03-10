#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_SCRIPT="${ROOT_DIR}/install.sh"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

pass() {
  echo "PASS: $1"
}

assert_file_contains() {
  local file="$1"
  local pattern="$2"
  if ! grep -qE "$pattern" "$file"; then
    fail "Expected ${file} to contain pattern: ${pattern}"
  fi
}

assert_file_not_contains() {
  local file="$1"
  local pattern="$2"
  if grep -qE "$pattern" "$file"; then
    fail "Did not expect ${file} to contain pattern: ${pattern}"
  fi
}

create_test_project() {
  local project_dir="$1"

  mkdir -p "${project_dir}/scripts"

  cat > "${project_dir}/.env.example" <<'EOF'
DEFAULT_LLM_PROVIDER=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
TAVILY_API_KEY=
CURRENCY_API_KEY=
EOF

  cat > "${project_dir}/docker-compose.local.yml" <<'EOF'
services: {}
EOF

  cat > "${project_dir}/scripts/bootstrap_local_secrets.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if ! grep -q '^BOOTSTRAPPED=1$' ".env" 2>/dev/null; then
  printf "BOOTSTRAPPED=1\n" >> ".env"
fi
EOF

  chmod +x "${project_dir}/scripts/bootstrap_local_secrets.sh"
}

run_main_with_overrides() {
  local project_dir="$1"
  local prompt_file="$2"
  local url_log="$3"
  local stack_log="$4"

  PROJECT_UNDER_TEST="$project_dir" \
  PROMPT_FILE="$prompt_file" \
  URL_LOG="$url_log" \
  STACK_LOG="$stack_log" \
  INSTALL_SCRIPT="$INSTALL_SCRIPT" \
  bash <<'EOF'
set -euo pipefail
cd "$PROJECT_UNDER_TEST"
export SV_INSTALL_PROMPT_FILE="$PROMPT_FILE"
source "$INSTALL_SCRIPT"
ensure_docker_ready() { DOCKER_CMD=("docker"); COMPOSE_CMD=("docker" "compose"); }
open_url() { printf "%s\n" "$1" >> "$URL_LOG"; return 0; }
start_stack() { printf "started\n" >> "$STACK_LOG"; }
main
EOF
}

test_interactive_setup_writes_keys() {
  local work_dir
  local prompt_file
  local url_log
  local stack_log

  work_dir="$(mktemp -d)"
  prompt_file="${work_dir}/answers.txt"
  url_log="${work_dir}/urls.log"
  stack_log="${work_dir}/stack.log"

  create_test_project "$work_dir"
  : > "$url_log"
  : > "$stack_log"

  cat > "$prompt_file" <<'EOF'
y
2
sk-openai-test
n
n
tvly-test-key
n
currency-test-key
EOF

  run_main_with_overrides "$work_dir" "$prompt_file" "$url_log" "$stack_log"

  assert_file_contains "${work_dir}/.env" '^OPENAI_API_KEY=sk-openai-test$'
  assert_file_contains "${work_dir}/.env" '^DEFAULT_LLM_PROVIDER=openai$'
  assert_file_contains "${work_dir}/.env" '^TAVILY_API_KEY=tvly-test-key$'
  assert_file_contains "${work_dir}/.env" '^CURRENCY_API_KEY=currency-test-key$'
  assert_file_contains "${work_dir}/.env" '^BOOTSTRAPPED=1$'
  assert_file_contains "$stack_log" '^started$'
  assert_file_not_contains "$url_log" '.'

  pass "interactive setup writes keys and starts the stack"
}

test_optional_llm_and_tavily_can_be_skipped() {
  local work_dir
  local prompt_file
  local url_log
  local stack_log

  work_dir="$(mktemp -d)"
  prompt_file="${work_dir}/answers.txt"
  url_log="${work_dir}/urls.log"
  stack_log="${work_dir}/stack.log"

  create_test_project "$work_dir"
  : > "$url_log"
  : > "$stack_log"

  cat > "$prompt_file" <<'EOF'
n
y
n

y
n
currency-only-key
EOF

  run_main_with_overrides "$work_dir" "$prompt_file" "$url_log" "$stack_log"

  assert_file_contains "${work_dir}/.env" '^DEFAULT_LLM_PROVIDER=$'
  assert_file_contains "${work_dir}/.env" '^OPENAI_API_KEY=$'
  assert_file_contains "${work_dir}/.env" '^TAVILY_API_KEY=$'
  assert_file_contains "${work_dir}/.env" '^CURRENCY_API_KEY=currency-only-key$'
  assert_file_contains "$stack_log" '^started$'

  pass "installer can skip optional LLM and Tavily setup"
}

test_macos_download_url_selection() {
  local arm_url
  local amd_url

  arm_url="$(
    INSTALL_SCRIPT="$INSTALL_SCRIPT" bash <<'EOF'
set -euo pipefail
source "$INSTALL_SCRIPT"
uname() {
  if [[ "${1:-}" == "-m" ]]; then
    echo "arm64"
  else
    command uname "$@"
  fi
}
docker_desktop_url_for_macos
EOF
  )"

  amd_url="$(
    INSTALL_SCRIPT="$INSTALL_SCRIPT" bash <<'EOF'
set -euo pipefail
source "$INSTALL_SCRIPT"
uname() {
  if [[ "${1:-}" == "-m" ]]; then
    echo "x86_64"
  else
    command uname "$@"
  fi
}
docker_desktop_url_for_macos
EOF
  )"

  [[ "$arm_url" == "https://desktop.docker.com/mac/main/arm64/Docker.dmg" ]] || fail "Unexpected arm64 Docker URL"
  [[ "$amd_url" == "https://desktop.docker.com/mac/main/amd64/Docker.dmg" ]] || fail "Unexpected amd64 Docker URL"

  pass "macOS Docker Desktop URLs are selected by architecture"
}

main() {
  test_interactive_setup_writes_keys
  test_optional_llm_and_tavily_can_be_skipped
  test_macos_download_url_selection
}

main "$@"
