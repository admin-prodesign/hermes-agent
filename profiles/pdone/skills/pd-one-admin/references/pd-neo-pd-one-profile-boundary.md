# PD Neo vs PD One Hermes profile boundary

Use this when deciding which Hermes profile owns an operation after the OpenClaw → Hermes migration.

## Boundary

- Default-profile Hermes (`HERMES_HOME=/home/prodesign/.hermes`) is PD Neo.
- Hermes profile `pdone` (`/home/prodesign/.hermes/profiles/pdone`) is PD One.
- PD One Mattermost permission/governance source-of-truth semantics live in the `pdone` profile, not in default-profile Hermes and not in legacy OpenClaw.

## Operational implications

- Verify the active process/profile before interpreting config or logs.
- A default-profile Hermes gateway/process is not evidence that PD One is misconfigured; it may be PD Neo.
- For PD One gateway checks, look for `--profile pdone` or `HERMES_HOME=/home/prodesign/.hermes/profiles/pdone`.
- For PD One permission/cache/policy changes, edit and back up the `pdone` profile’s durable state.
- Do not modify another Hermes profile’s skills/plugins/cron/memories unless Andy explicitly asks.

## Reporting wording

Prefer: “PD One is cut over in the `pdone` profile; default-profile Hermes is PD Neo.”

Avoid: “There is an extra default Hermes gateway, so PD One might not be cut over” unless you have verified that process is actually handling PD One traffic.