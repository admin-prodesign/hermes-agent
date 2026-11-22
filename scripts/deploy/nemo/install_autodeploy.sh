#!/usr/bin/env bash
# Install or remove the pull-deploy units. Run it from releases/current, so the
# units and the code they start come from the same deployed release.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${here}/common.sh"

case "${1:-}" in
  -h|--help|"")
    cat <<'EOF'
Usage: install_autodeploy.sh install --mirror DIR [options]
       install_autodeploy.sh uninstall [--scope user|system]

  --mirror DIR                  Bare mirror build.sh uses. Its remote must already
                                fetch the private repo non-interactively.
  --remote NAME                 Mirror remote to poll. Default origin.
  --hermes-home PATH            Defaults to HERMES_HOME.
  --scope user|system           Default user (needs `loginctl enable-linger`).
  --poll-every SPAN             systemd time span between polls. Default 60s (+ up to 20s jitter).
  --alert-script PATH           Called as PATH SUBJECT with the details on stdin.
  --profile NAME                Repeatable. Default pdone, then default (PD Neo).
  --run-as USER                 System scope: user for the poll and drift check.
  --worker-user USER            System scope: user for the deploy worker.
  --canary                      Restart deploys restart and verify PD Neo before pdone.
  --dry-run                     Print the units and change nothing.

Nothing to set up in GitHub or Tailscale. A leftover hermes-deploy-listener.service
from the push version is disabled and removed. See scripts/deploy/nemo/README.md.
EOF
    exit 0
    ;;
esac

nemo_python -m scripts.deploy.nemo.autodeploy_units "$@"
