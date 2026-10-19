#!/usr/bin/env bash
# Restore the previous release links, unit files and drop-ins, and configs from an audit manifest.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${here}/common.sh"

usage() {
  cat <<'EOF'
Usage: rollback.sh --manifest PATH [--no-restart]

Restores unit files, drop-ins, and configs from the backups named in the manifest,
then puts back releases/current, previous, the runtime links, and .running. Then
daemon-reload and restart the units the cutover restarted. The new release
directory is left in place. --no-restart skips systemctl.
EOF
}

manifest=""
no_restart=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest) manifest="${2:-}"; shift 2 ;;
    --no-restart) no_restart=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -n "${manifest}" ]] || die "pass --manifest"
[[ -f "${manifest}" ]] || die "manifest missing: ${manifest}"
nemo_python -m scripts.deploy.nemo.cli rollback --manifest "${manifest}"
if [[ "${no_restart}" != "1" ]]; then
  restart_units "${manifest}"
fi
printf '%s\n' "rolled back ${manifest}"
