#!/usr/bin/env bash
# Restore the previous release symlink, unit files, and configs from an audit manifest.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${here}/common.sh"

usage() {
  cat <<'EOF'
Usage: rollback.sh --manifest PATH [--no-restart]

Restores unit files and configs from the backups named in the manifest, then
points releases/current at the previous build. The new release directory is
left in place. --no-restart skips systemctl.
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
