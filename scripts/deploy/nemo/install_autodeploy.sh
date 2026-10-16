#!/usr/bin/env bash
# Install or remove the push-deploy units. Run it from releases/current, so the
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

  --hermes-home PATH            Defaults to HERMES_HOME.
  --scope user|system           Default user (needs `loginctl enable-linger`).
  --bind ADDR / --port N        Listener address. Default 127.0.0.1:8765.
  --require-tailscale-tag TAG   Also check the peer's Tailscale tag (direct bind only).
  --alert-script PATH           Called as PATH SUBJECT with the details on stdin.
  --profile NAME                Repeatable. Default pdone, then pdneo.
  --run-as USER                 System scope: user for the listener and drift check.
  --worker-user USER            System scope: user for the deploy worker.
  --dry-run                     Print the units and change nothing.

Creates <home>/deploy/webhook-secret (0600) on first install. See
scripts/deploy/nemo/README.md for the one-time GitHub and Tailscale setup.
EOF
    exit 0
    ;;
esac

nemo_python -m scripts.deploy.nemo.autodeploy_units "$@"
