# Hermes dashboard over Tailscale for PD One

Use when the Hermes dashboard URL on `nemo.tail05d15a.ts.net` does not load, returns 502, or shows host-header/auth/bind errors. This is a PD One admin runtime pattern, not an employee-facing workflow.

## Current intended shape

- Tailnet URL: `https://nemo.tail05d15a.ts.net/?profile=pdone`
- User systemd service: `/home/prodesign/.config/systemd/user/hermes-dashboard.service`
- Tailscale Serve route: `https://nemo.tail05d15a.ts.net/` proxies to `http://nemo.tail05d15a.ts.net:8765`
- Dashboard profile hint: use `?profile=pdone` or `/cron?profile=pdone` to select PD One.
- Do **not** restart the PD One messaging gateway just to repair the dashboard; check/repair the dashboard service and Tailscale Serve separately.

## Fast triage

1. Check DNS/Tailscale identity:
   - `getent hosts nemo.tail05d15a.ts.net`
   - `tailscale serve status`
2. Check dashboard service and port:
   - `systemctl --user status hermes-dashboard.service --no-pager -l`
   - `ss -ltnp | grep ':8765'`
3. Check HTTP receipts:
   - `curl -sS --max-time 20 'https://nemo.tail05d15a.ts.net/?profile=pdone' -o /tmp/dashboard.html -w 'status=%{http_code} bytes=%{size_download} time=%{time_total}\n'`
   - `grep -o '<title>[^<]*</title>' /tmp/dashboard.html`
4. If Tailscale returns 502, the dashboard backend is usually down, bound to the wrong host, or Tailscale Serve points at the wrong local target.

## Known-good service pattern

The service should run the Hermes dashboard on the Tailscale hostname and port used by Tailscale Serve, for example:

```ini
[Unit]
Description=Hermes Agent Web Dashboard
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/prodesign
Environment=HERMES_HOME=/home/prodesign/.hermes/profiles/pdone
Environment=PATH=/home/prodesign/.local/bin:/home/prodesign/.hermes/runtime/current/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/home/prodesign/.local/bin/hermes --profile pdone dashboard --host nemo.tail05d15a.ts.net --port 8765 --no-open --skip-build --insecure
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-dashboard.service
tailscale serve --bg http://nemo.tail05d15a.ts.net:8765
```

## Host-header / auth pitfall

Hermes dashboard validates the Host header. A common failure path is:

- dashboard bound to `127.0.0.1`, but browser reaches it as `nemo.tail05d15a.ts.net`
- Tailscale Serve proxies to a loopback backend and preserves a Host header the app rejects
- symptom: `Invalid Host header. Dashboard requests must use the hostname the server was bound to.`

Bind the dashboard to `nemo.tail05d15a.ts.net` and set Tailscale Serve to proxy to the same hostname/port. If Hermes refuses a non-loopback bind because no dashboard auth provider is registered, `--insecure` may be needed for a tailnet-only deployment. Treat that as a security caveat: tailnet-only is not the same as authenticated; prefer future dashboard auth or Tailscale ACL restriction when practical.

## Web UI build / dependency pitfall

If the dashboard service exits with missing Python dependencies or `web_dist`, do **not** install into `/home/prodesign/.hermes/runtime/current`; that path is the immutable production release. Prepare a new release worktree from the approved custom-runtime SHA, build its locked Python environment with `uv sync`, build the web UI in that candidate, verify the candidate independently, then route/restart only `hermes-dashboard.service` through the normal activation gate. Preserve the current release as rollback until verification passes.

The dashboard may perform one bounded recovery build when `--skip-build` finds no `web_dist`, but a durable repair belongs in the next immutable release rather than an editable install in production.

## Verification receipts

A successful repair should capture all of these:

- `systemctl --user is-active hermes-dashboard.service` -> `active`
- `systemctl --user is-enabled hermes-dashboard.service` -> `enabled`
- `tailscale serve status` shows `https://nemo.tail05d15a.ts.net` proxying to `http://nemo.tail05d15a.ts.net:8765`
- `curl` to `https://nemo.tail05d15a.ts.net/?profile=pdone` returns HTTP 200 and the title `Hermes Agent - Dashboard`
- Browser or dashboard snapshot shows the amber “Managing profile “pdone”” banner when using `?profile=pdone`.

## Cleanup / backup

- Disable stale services that occupy the intended backend port or create confusion, but do not delete them unless explicitly approved.
- If npm/pip work creates transient checkout changes such as `build/` or package-lock noise, clean or revert them before reporting.
- Run the configured Hermes backup helper after durable service/profile changes and report the backup commit when available.
