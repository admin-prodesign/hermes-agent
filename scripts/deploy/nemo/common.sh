# Shared helpers for the nemo deploy scripts. Source this file; do not execute it.
# shellcheck shell=bash

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  printf '%s\n' "source scripts/deploy/nemo/common.sh; do not execute it" >&2
  exit 1
fi

nemo_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
nemo_repo="$(cd "${nemo_here}/../../.." && pwd)"

# uv and other user-local tools (matches service_path_env in autodeploy_units.py).
export PATH="${HOME}/.local/bin:${PATH}"

if [[ -z "${NEMO_PYTHON:-}" ]]; then
  if command -v python >/dev/null 2>&1; then
    NEMO_PYTHON="$(command -v python)"
  elif command -v python3 >/dev/null 2>&1; then
    NEMO_PYTHON="$(command -v python3)"
  else
    printf '%s\n' "python is required" >&2
    return 1
  fi
fi

die() {
  printf '%s\n' "$*" >&2
  exit 1
}

nemo_python() {
  local prefix="${nemo_repo}"
  if [[ -n "${PYTHONPATH:-}" ]]; then
    prefix="${nemo_repo}:${PYTHONPATH}"
  fi
  PYTHONPATH="${prefix}" "${NEMO_PYTHON}" "$@"
}

run_systemctl() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 30 systemctl "$@"
  else
    systemctl "$@"
  fi
}

restart_units() {
  local manifest="$1"
  local lines kind path name
  local saw_system=0
  local saw_user=0
  local any=0
  lines="$(nemo_python -m scripts.deploy.nemo.cli list-units --manifest "${manifest}")"
  while IFS=$'\t' read -r kind path; do
    [[ -n "${path:-}" ]] || continue
    any=1
    name="$(basename "${path}")"
    if [[ "${kind}" == "user" ]]; then
      if [[ "${saw_user}" == "0" ]]; then
        run_systemctl --user daemon-reload
        saw_user=1
      fi
      run_systemctl --user restart "${name}"
    else
      if [[ "${saw_system}" == "0" ]]; then
        run_systemctl daemon-reload
        saw_system=1
      fi
      run_systemctl restart "${name}"
    fi
  done <<< "${lines}"
  if [[ "${any}" == "0" ]]; then
    printf '%s\n' "warning: no systemd units to restart" >&2
  fi
}
