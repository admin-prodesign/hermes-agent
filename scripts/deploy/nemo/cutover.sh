#!/usr/bin/env bash
# Swap releases/current onto a built release, poll health, then run safe cron checks.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${here}/common.sh"

usage() {
  cat <<'EOF'
Usage: cutover.sh --build NAME [options]

  --hermes-home PATH      Profile home. Defaults to HERMES_HOME.
  --releases PATH         Release root. Defaults to <home>/releases.
  --sha SHA               New commit. Defaults to the build manifest.
  --mirror DIR            Bare mirror used to diff the old and new SHA.
  --old-sha SHA           Previous commit. Defaults to the previous build manifest.
  --full                  Run every verify and the deploy tests.
  --profile NAME          Repeatable. Default order is pdone, then pdneo.
  --unit-dir PATH         Repeatable. Default: system and user systemd dirs.
  --quiet SEC             Newest message must be at least this old. Default: 90.
  --poll SEC              Gate poll interval. Default: 30.
  --gate-timeout SEC      Default: 600.
  --gateway-health URL    Default: http://127.0.0.1:8642/health
  --dashboard-health URL  Default: http://127.0.0.1:9119/api/health
  --health-timeout SEC    Default: 90.
  --health-interval SEC   Default: 2.
  --skip-preflight        Skip diff-scoped verifies and pytest.
  --skip-pytest           Run verifies, and leave pytest to CI.
  --skip-gate             Do not wait for a quiet window.
  --skip-restart          Do not systemctl restart.
  --skip-health           Do not poll. A failed poll rolls the release back.
  --skip-postcheck        Do not run the cron jobs' safe checks.

The gate still requires no leases, a newest message at least --quiet seconds
old, and no live goal. HR sync is dry-run only during the post-check.
EOF
}

home="${HERMES_HOME:-}"
build=""
sha=""
releases=""
mirror=""
old_sha=""
full=0
skip_pytest=0
skip_preflight=0
skip_gate=0
skip_restart=0
skip_health=0
skip_postcheck=0
quiet="90"
poll="30"
gate_timeout="600"
health_timeout="90"
health_interval="2"
gateway="http://127.0.0.1:8642/health"
dashboard="http://127.0.0.1:9119/api/health"
profiles=()
unit_dirs=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hermes-home) home="${2:-}"; shift 2 ;;
    --build) build="${2:-}"; shift 2 ;;
    --sha) sha="${2:-}"; shift 2 ;;
    --releases) releases="${2:-}"; shift 2 ;;
    --mirror) mirror="${2:-}"; shift 2 ;;
    --old-sha) old_sha="${2:-}"; shift 2 ;;
    --full) full=1; shift ;;
    --profile) profiles+=("${2:-}"); shift 2 ;;
    --unit-dir) unit_dirs+=("${2:-}"); shift 2 ;;
    --quiet) quiet="${2:-}"; shift 2 ;;
    --poll) poll="${2:-}"; shift 2 ;;
    --gate-timeout) gate_timeout="${2:-}"; shift 2 ;;
    --gateway-health) gateway="${2:-}"; shift 2 ;;
    --dashboard-health) dashboard="${2:-}"; shift 2 ;;
    --health-timeout) health_timeout="${2:-}"; shift 2 ;;
    --health-interval) health_interval="${2:-}"; shift 2 ;;
    --skip-preflight) skip_preflight=1; shift ;;
    --skip-pytest) skip_pytest=1; shift ;;
    --skip-gate) skip_gate=1; shift ;;
    --skip-restart) skip_restart=1; shift ;;
    --skip-health) skip_health=1; shift ;;
    --skip-postcheck) skip_postcheck=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -n "${home}" ]] || die "pass --hermes-home or set HERMES_HOME"
[[ -n "${build}" ]] || die "pass --build"
if [[ -z "${releases}" ]]; then
  releases="${home}/releases"
fi
release="${releases}/${build}"
manifest="${home}/upgrade-audits/${build}/manifest.json"
[[ -f "${release}/pyproject.toml" ]] || die "release is missing or has no pyproject.toml: ${release}"
venv_python="${release}/.venv/bin/python"
[[ -x "${venv_python}" ]] || die "release interpreter missing: ${venv_python}"

if [[ -z "${sha}" && -f "${manifest}" ]]; then
  sha="$(nemo_python -m scripts.deploy.nemo.cli manifest-get --path "${manifest}" --key sha || true)"
fi
if [[ -z "${old_sha}" && -L "${releases}/current" ]]; then
  previous_name="$(basename "$(readlink "${releases}/current")")"
  old_manifest="${home}/upgrade-audits/${previous_name}/manifest.json"
  if [[ -f "${old_manifest}" ]]; then
    old_sha="$(nemo_python -m scripts.deploy.nemo.cli manifest-get --path "${old_manifest}" --key sha || true)"
  fi
fi

profile_args=()
if [[ "${#profiles[@]}" -gt 0 ]]; then
  for name in "${profiles[@]}"; do
    profile_args+=(--profile "${name}")
  done
fi

run_verify() {
  case "$1" in
    verify_mcp)
      nemo_python -m scripts.deploy.nemo.cli verify-mcp \
        --hermes-home "${home}" --release "${release}" --python "${venv_python}" \
        "${profile_args[@]}"
      ;;
    verify_ws)
      nemo_python -m scripts.deploy.nemo.cli verify-ws --release "${release}"
      ;;
    *)
      die "unknown verify: $1"
      ;;
  esac
}

run_selected_tests() {
  if [[ "$#" -eq 0 ]]; then
    return 0
  fi
  if [[ "${skip_pytest}" == "1" ]]; then
    printf '%s\n' "skipping pytest; CI runs the unit tests"
    return 0
  fi
  if ! nemo_python -c "import pytest" >/dev/null 2>&1; then
    printf '%s\n' "pytest is not installed here; CI runs the unit tests"
    return 0
  fi
  (cd "${nemo_repo}" && scripts/run_tests.sh "$@")
}

run_preflight() {
  local plan_output kind name
  local -a plan_args tests
  plan_args=(-m scripts.deploy.nemo.cli plan --new "${sha:-unknown}")
  if [[ "${full}" == "1" ]]; then
    plan_args+=(--full)
  elif [[ -n "${mirror}" && -n "${old_sha}" ]]; then
    plan_args+=(--mirror "${mirror}" --old "${old_sha}")
  fi
  plan_output="$(nemo_python "${plan_args[@]}")"
  printf '%s\n' "${plan_output}"
  tests=()
  while read -r kind name; do
    case "${kind:-}" in
      VERIFY) run_verify "${name}" ;;
      TEST) tests+=("${name}") ;;
      *) ;;
    esac
  done <<< "${plan_output}"
  if [[ "${#tests[@]}" -gt 0 ]]; then
    run_selected_tests "${tests[@]}"
  fi
}

if [[ "${skip_preflight}" != "1" ]]; then
  run_preflight
fi

if [[ "${skip_gate}" != "1" ]]; then
  nemo_python -m scripts.deploy.nemo.cli gate \
    --hermes-home "${home}" --quiet "${quiet}" --poll "${poll}" --timeout "${gate_timeout}" \
    "${profile_args[@]}"
fi

cut_args=(
  -m scripts.deploy.nemo.cli cutover
  --hermes-home "${home}" --releases "${releases}" --build "${build}"
)
if [[ "${#unit_dirs[@]}" -gt 0 ]]; then
  for dir in "${unit_dirs[@]}"; do
    cut_args+=(--unit-dir "${dir}")
  done
fi
nemo_python "${cut_args[@]}"

if [[ "${skip_restart}" != "1" ]]; then
  restart_units "${manifest}"
fi

if [[ "${skip_health}" != "1" ]]; then
  if ! nemo_python -m scripts.deploy.nemo.cli health \
      --manifest "${manifest}" \
      --gateway-url "${gateway}" \
      --dashboard-url "${dashboard}" \
      --timeout "${health_timeout}" \
      --interval "${health_interval}"; then
    printf '%s\n' "health check failed; rolling back" >&2
    bash "${here}/rollback.sh" --manifest "${manifest}" || printf '%s\n' "rollback did not finish cleanly" >&2
    exit 1
  fi
fi

if [[ "${skip_postcheck}" != "1" ]]; then
  nemo_python -m scripts.deploy.nemo.cli postcheck \
    --hermes-home "${home}" --python "${venv_python}" "${profile_args[@]}"
fi
printf '%s\n' "cutover ${build} is live"
