#!/usr/bin/env bash
# Gate the new release, swap releases/current onto it, render the units against it,
# restart and verify in stages, poll health, then run safe cron checks.
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
  --profile NAME          Repeatable. Default order is pdone, then default (PD Neo).
  --unit-dir PATH         Repeatable. Default: system and user systemd dirs.
  --quiet SEC             Newest message must be at least this old. Default: 90.
  --poll SEC              Gate poll interval. Default: 30.
  --gate-timeout SEC      Default: 600.
  --stale-goal-s SEC      Ignore active 0-turn goals older than this. Default: 604800 (7 days).
  --gateway-health URL    Default: http://127.0.0.1:8644/health (PD Neo on nemo).
  --dashboard-health URL  Default: http://127.0.0.1:8765/api/health.
  --socket-profile NAME   Repeatable. Gateway control-socket check (default: pdone, default).
  --health-timeout SEC    Default: 90.
  --health-interval SEC   Default: 2.
  --skip-preflight        Skip diff-scoped verifies and pytest.
  --skip-selftest         Skip the PD One safe-ops selftest against the new release.
  --selftest-profile NAME Profile the selftest reads pd_one config from. Default: pdone.
  --selftest-allow-missing KEY
                          Repeatable. pd_one.external key that is absent on this host on purpose.
  --skip-pytest           Run verifies, and leave pytest to CI.
  --skip-adapter-gate     Do not dry-start the enabled gateway adapters from the new release.
  --gateway-unit P=UNIT   Repeatable. Gateway unit of profile P. Default: hermes-gateway.service
                          for the top-level profile, hermes-gateway-<P>.service otherwise.
  --runtime-link PATH     Repeatable. Symlink into a release to retarget.
                          Default: <releases>/runtime/current when it exists.
  --skip-gate             Do not wait for a quiet window.
  --skip-restart          Do not systemctl restart (also skips the adapter gate and verify).
  --canary                Restart and verify the top-level profile (PD Neo) first, then the
                          others; a failed stage rolls everything back before pdone restarts.
  --expect P=PLATFORM     Repeatable. Adapter that must report connected after the restart.
                          Default: deploy.verify.<P>.platforms, else what the adapter gate started.
  --expect-port P=PORT    Repeatable. Port that must accept connections after the restart.
                          Default: deploy.verify.<P>.ports.
  --port-host HOST        Host the port check connects to. Default: 127.0.0.1.
  --skip-verify           Do not check adapters and ports after the restart.
  --skip-health           Do not poll. A failed poll rolls the release back.
  --skip-postcheck        Do not run the cron jobs' safe checks.

Before the idle gate, every enabled adapter of every profile is created (not connected)
by the new release's interpreter with the environment its rendered gateway unit gives
it; a failure refuses the cutover with nothing changed. The cutover renders every unit
and drop-in against the new release (paths, .venv/bin for a missing .hermes/bin wrapper,
HERMES_RUNTIME_SHA) and refuses if a rendered unit names a path the release lacks.

The gate still requires no leases, a newest message at least --quiet seconds
old, and no live goal (stale 0-turn goals older than --stale-goal-s are
ignored). A missing state.db for a configured profile fails immediately.
Exit 75 means the gate timed out or the database was missing; nothing changed.
HR sync is dry-run only during the post-check.
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
skip_selftest=0
selftest_profile="pdone"
selftest_allow_missing=()
skip_gate=0
skip_restart=0
skip_health=0
skip_postcheck=0
quiet="90"
poll="30"
gate_timeout="600"
stale_goal_s="604800"
health_timeout="90"
health_interval="2"
gateway=""
dashboard=""
socket_profiles=()
profiles=()
unit_dirs=()
skip_adapter_gate=0
skip_verify=0
canary=0
port_host=""
gateway_units=()
runtime_links=()
expects=()
expect_ports=()

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
    --stale-goal-s) stale_goal_s="${2:-}"; shift 2 ;;
    --gateway-health) gateway="${2:-}"; shift 2 ;;
    --dashboard-health) dashboard="${2:-}"; shift 2 ;;
    --health-timeout) health_timeout="${2:-}"; shift 2 ;;
    --health-interval) health_interval="${2:-}"; shift 2 ;;
    --skip-preflight) skip_preflight=1; shift ;;
    --skip-selftest) skip_selftest=1; shift ;;
    --selftest-profile) selftest_profile="${2:-}"; shift 2 ;;
    --selftest-allow-missing) selftest_allow_missing+=("${2:-}"); shift 2 ;;
    --skip-pytest) skip_pytest=1; shift ;;
    --skip-gate) skip_gate=1; shift ;;
    --skip-restart) skip_restart=1; shift ;;
    --skip-health) skip_health=1; shift ;;
    --skip-postcheck) skip_postcheck=1; shift ;;
    --skip-adapter-gate) skip_adapter_gate=1; shift ;;
    --skip-verify) skip_verify=1; shift ;;
    --canary) canary=1; shift ;;
    --port-host) port_host="${2:-}"; shift 2 ;;
    --gateway-unit) gateway_units+=("${2:-}"); shift 2 ;;
    --runtime-link) runtime_links+=("${2:-}"); shift 2 ;;
    --expect) expects+=("${2:-}"); shift 2 ;;
    --expect-port) expect_ports+=("${2:-}"); shift 2 ;;
    --socket-profile) socket_profiles+=("${2:-}"); shift 2 ;;
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
  (cd "${nemo_repo}" && bash scripts/run_tests.sh "$@")
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

# Every safe-ops tool, called harmlessly from the new read-only release with the live profile's
# config, before anything is swapped.
run_selftest() {
  local -a args=(--hermes-home "${home}" --profile "${selftest_profile}")
  local key
  if [[ "${#selftest_allow_missing[@]}" -gt 0 ]]; then
    for key in "${selftest_allow_missing[@]}"; do
      args+=(--allow-missing "${key}")
    done
  fi
  (cd "${release}" && "${venv_python}" -m tools.pd_one_ops.selftest "${args[@]}")
}

if [[ "${skip_selftest}" != "1" ]]; then
  run_selftest || die "pd-one safe-ops selftest failed against ${release}; nothing was changed"
fi

unit_dir_args=()
for dir in "${unit_dirs[@]}"; do
  unit_dir_args+=(--unit-dir "${dir}")
done
gateway_unit_args=()
for item in "${gateway_units[@]}"; do
  gateway_unit_args+=(--gateway-unit "${item}")
done

# A no-restart deploy never loads the new release into a gateway, so only a restart is gated.
if [[ "${skip_restart}" != "1" && "${skip_adapter_gate}" != "1" ]]; then
  gate_args=(
    -m scripts.deploy.nemo.cli adapter-gate
    --hermes-home "${home}" --releases "${releases}" --build "${build}"
    "${unit_dir_args[@]}" "${gateway_unit_args[@]}" "${profile_args[@]}"
  )
  if [[ -n "${sha}" ]]; then
    gate_args+=(--sha "${sha}")
  fi
  nemo_python "${gate_args[@]}" || die "adapter gate failed against ${release}; nothing was changed"
fi

if [[ "${skip_gate}" != "1" ]]; then
  if ! nemo_python -m scripts.deploy.nemo.cli gate \
      --hermes-home "${home}" --quiet "${quiet}" --poll "${poll}" --timeout "${gate_timeout}" \
      --stale-goal-s "${stale_goal_s}" "${profile_args[@]}"; then
    printf '%s\n' "profiles never went quiet; nothing was changed" >&2
    exit 75
  fi
fi

cut_args=(
  -m scripts.deploy.nemo.cli cutover
  --hermes-home "${home}" --releases "${releases}" --build "${build}"
)
if [[ -n "${sha}" ]]; then
  cut_args+=(--sha "${sha}")
fi
cut_args+=("${unit_dir_args[@]}")
for link in "${runtime_links[@]}"; do
  cut_args+=(--runtime-link "${link}")
done
if [[ "${skip_restart}" != "1" ]]; then
  cut_args+=(--running)
fi
nemo_python "${cut_args[@]}"

if [[ "${skip_restart}" != "1" ]]; then
  rollout_args=(
    -m scripts.deploy.nemo.cli rollout
    --hermes-home "${home}" --manifest "${manifest}"
    --timeout "${health_timeout}" --interval "${health_interval}"
    "${gateway_unit_args[@]}" "${profile_args[@]}"
  )
  if [[ "${canary}" == "1" ]]; then
    rollout_args+=(--canary)
  fi
  if [[ "${skip_verify}" == "1" ]]; then
    rollout_args+=(--skip-verify)
  fi
  if [[ -n "${port_host}" ]]; then
    rollout_args+=(--port-host "${port_host}")
  fi
  for item in "${expects[@]}"; do
    rollout_args+=(--expect "${item}")
  done
  for item in "${expect_ports[@]}"; do
    rollout_args+=(--expect-port "${item}")
  done
  if ! nemo_python "${rollout_args[@]}"; then
    printf '%s\n' "restart or adapter verify failed; rolling back" >&2
    bash "${here}/rollback.sh" --manifest "${manifest}" || printf '%s\n' "rollback did not finish cleanly" >&2
    exit 1
  fi
fi

if [[ "${skip_health}" != "1" ]]; then
  health_args=(
    -m scripts.deploy.nemo.cli health
    --hermes-home "${home}"
    --manifest "${manifest}"
    --timeout "${health_timeout}"
    --interval "${health_interval}"
  )
  if [[ -n "${gateway}" ]]; then
    health_args+=(--gateway-url "${gateway}")
  fi
  if [[ -n "${dashboard}" ]]; then
    health_args+=(--dashboard-url "${dashboard}")
  fi
  for prof in "${socket_profiles[@]}"; do
    health_args+=(--socket-profile "${prof}")
  done
  if ! nemo_python "${health_args[@]}"; then
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
