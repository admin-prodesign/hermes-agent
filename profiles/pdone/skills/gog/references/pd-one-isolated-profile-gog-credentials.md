# PD One isolated-profile Gog credentials

Use this when PD One/Hermes runs with an isolated profile `HOME` and `gog auth list` reports no accounts or unreadable file-keyring tokens, while the host user already has an approved Gog OAuth setup.

## Symptom pattern

- Active runtime `HOME` is a profile home such as `/home/prodesign/.hermes/profiles/pdone/home`.
- Host Gog config exists under `/home/prodesign/.config/gogcli`.
- Profile-local Gog config/keyring is missing, symlinked incorrectly, or cannot read the file-keyring token because the file-keyring password is not available in the profile environment.
- The approved requirement is to avoid Gmail send access.

## Safe repair pattern

1. Treat this as credential/config work: require approved-user authorization before copying/importing tokens.
2. Do not print token contents or keyring password values.
3. Copy Gog config, OAuth client JSON, and file keyring from the host credential home into the isolated profile home:
   - source: `/home/prodesign/.config/gogcli`
   - destination: `/home/prodesign/.hermes/profiles/pdone/home/.config/gogcli`
4. Copy only the needed OpenClaw Gog keyring password file into the profile OpenClaw config directory so the shared wrapper can unlock the copied file keyring:
   - source: `/home/prodesign/.config/openclaw/gog_keyring_password`
   - destination: `/home/prodesign/.hermes/profiles/pdone/home/.config/openclaw/gog_keyring_password`
   - permissions: `0600`
5. Use a profile-local `gog` shim that delegates to OpenClaw's shared wrapper instead of bypassing safety rails:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec /home/prodesign/.openclaw/workspace/scripts/google/gog.sh "$@"
```

6. Keep the shared wrapper's Gmail-send safety rail active. Do not set `GOG_ALLOW_GMAIL_SEND=1` unless there is explicit email-send approval.

## Verification checklist

Run from the PD One profile runtime, where `command -v gog` should resolve to the profile-local shim:

```bash
command -v gog
gog --version
gog auth status --json --no-input
gog auth list --json --no-input
gog auth doctor --json --no-input
```

Verify all of the following:

- `gog auth status` points at the profile-local config path.
- `gog auth list` shows the expected account and no token-read errors.
- `gog auth doctor` reports `status: ok` and at least one readable OAuth token.
- No scopes contain `gmail` when the request was "without Gmail".
- A Gmail send smoke test is blocked by the wrapper, for example `gog gmail send --help` exits with the wrapper's Gmail-send block message.

## Pitfalls

- A symlink from profile config to host config may still fail if the wrapper/keyring password lookup depends on `HOME`; prefer a profile-local copy plus the profile-local OpenClaw keyring password file.
- Exporting and importing the token with `gog auth tokens export/import` can fail in non-interactive shells if `GOG_KEYRING_PASSWORD` is not available; copying the encrypted keyring plus the password file avoids printing or rewrapping the token.
- Do not wrap `/home/prodesign/.local/bin/gog` directly if that path is itself a wrapper; delegate to OpenClaw's shared `scripts/google/gog.sh` so Gmail-send blocking and keyring-password loading stay centralized.
- Commit local Hermes/OpenClaw backup state after durable profile changes when a backup repo is configured; report if push fails due missing GitHub credentials.
