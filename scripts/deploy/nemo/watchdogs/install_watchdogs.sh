#!/usr/bin/env bash
# Install or remove the nemo no-agent watchdog units. Run it from
# releases/current so the units and the code they start come from the same
# deployed release.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../common.sh
source "${here}/../common.sh"

case "${1:-}" in
  -h|--help|"")
    cat <<'EOF'
Usage: install_watchdogs.sh install [options]
       install_watchdogs.sh uninstall [--scope user|system]
       install_watchdogs.sh --dry-run [install options]

  --hermes-home PATH   Defaults to HERMES_HOME
  --scope user|system  Default user (needs `loginctl enable-linger`)
  --enable             Enable and start timers (default: preserve enable state)
  --dry-run            Print the units and change nothing

Copy webhook.env.template to $HERMES_HOME/watchdogs/webhook.env (mode 0600)
before enabling. The installer never enables timers unless --enable is passed.
See scripts/deploy/nemo/README.md.
EOF
    exit 0
    ;;
esac

if [[ "${1:-}" == "--dry-run" ]]; then
  shift
  set -- install --dry-run "$@"
fi

nemo_python -m scripts.deploy.nemo.watchdogs.install "$@"
