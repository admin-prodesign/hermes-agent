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

# daemon-reload, restart the units a rollout restarted with the verbs it used, then verify.
# Unit files must already be restored for a rollback.
restart_units() {
  local manifest="$1"
  shift
  nemo_python -m scripts.deploy.nemo.cli restart --manifest "${manifest}" "$@"
}
