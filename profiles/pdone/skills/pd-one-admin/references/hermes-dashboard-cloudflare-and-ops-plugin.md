# Hermes Dashboard via Cloudflare Access + PD One Ops Plugin

Use this reference when Andy asks to expose the PD One/nemo Hermes dashboard beyond Tailscale, diagnose dashboard spinner/events-feed issues behind Cloudflare Access, or add PD One-specific dashboard tabs/plugins.

## Target architecture

```text
https://nemo.andyylin.com
  -> Cloudflare Access login/policy
  -> existing cloudflared tunnel on nemo
  -> http://127.0.0.1:8765
  -> hermes --profile pdone dashboard
```

Keep the dashboard origin loopback-only. Do **not** expose Hermes dashboard directly on a public interface. Cloudflare Access must sit in front of the route.

## Local Cloudflare tunnel pattern

In `/home/prodesign/.cloudflared/config.yml`, add the dashboard ingress before the final catch-all route:

```yaml
  - hostname: nemo.andyylin.com
    service: http://127.0.0.1:8765
    originRequest:
      httpHostHeader: localhost
```

Validate before restarting cloudflared:

```bash
cloudflared tunnel --config /home/prodesign/.cloudflared/config.yml ingress validate
```

Restart only after explicit approval if the tunnel also carries production webhooks:

```bash
systemctl --user restart cloudflared-pd-one-line.service
```

Verify route matching did not break existing host/path ingress, especially `pd-one-line.andyylin.com` webhook routes:

```bash
cloudflared tunnel --config /home/prodesign/.cloudflared/config.yml ingress rule https://pd-one-line.andyylin.com/line/webhook
cloudflared tunnel --config /home/prodesign/.cloudflared/config.yml ingress rule https://pd-one-line.andyylin.com/appsheet/case-update-mattermost
```

## Dashboard service pattern

Use a user service such as `/home/prodesign/.config/systemd/user/hermes-dashboard.service` and bind to loopback:

```text
ExecStart=/home/prodesign/.local/bin/hermes --profile pdone dashboard --host 127.0.0.1 --port 8765 --no-open --skip-build
```

If web dependencies or `web_dist` are missing after an update, do not mutate `/home/prodesign/.hermes/runtime/current`. Build and verify a fresh immutable release from the approved custom-runtime SHA (`uv sync` plus the web build in the candidate), then route/restart only `hermes-dashboard.service` through the normal activation gate. Keep the current release as rollback until the replacement returns HTTP 200 and its startup log is clean.

```bash
systemctl --user restart hermes-dashboard.service
curl -sS --max-time 15 http://127.0.0.1:8765/ -o /tmp/hermes_dash.html -w 'status=%{http_code} bytes=%{size_download}\n'
grep -o '<title>[^<]*</title>' /tmp/hermes_dash.html
```

Cloudflare-side unauthenticated checks should return an Access redirect, not the dashboard HTML:

```bash
curl -sS -I --max-time 20 https://nemo.andyylin.com/
# Expect HTTP 302 to https://andyylin.cloudflareaccess.com/...
```

## Spinner / events-feed disconnected / 400 behind Cloudflare

Symptom A: page loads or partly renders, but chats/tool events are missing and the dashboard says `events feed disconnected - tool calls may not appear`.

Common durable cause: HTTP origin proxying works, but WebSocket origin checks reject browser upgrades because Hermes is bound to `127.0.0.1` while browser `Origin` is `https://nemo.andyylin.com`.

Correct fix class:

- keep dashboard bound to loopback;
- require the immediate peer to be loopback;
- accept reverse-proxied WebSocket origins only when `Origin` matches `X-Forwarded-Host` from the trusted local proxy path;
- avoid broad `--insecure` or `0.0.0.0` exposure as the default fix.

Symptom B: after Cloudflare Access login, browser shows `400 Bad Request` from the dashboard/origin.

Common durable cause: Hermes' HTTP Host-header DNS-rebinding guard accepts `localhost`/`127.0.0.1` for loopback binds, but Cloudflare/cloudflared may forward the public host (`Host: nemo.andyylin.com`) to the loopback origin. The origin then returns `Invalid Host header` even though Cloudflare Access itself succeeded.

Correct fix class:

- keep dashboard bound to `127.0.0.1:8765`;
- allow reverse-proxied HTTP Host headers only when the TCP peer is loopback and `Host` matches `X-Forwarded-Host`;
- continue rejecting direct spoofed `Host: nemo.andyylin.com` requests without the trusted forwarded header;
- validate this separately from Cloudflare Access policy/login problems.

Verification recipes:

1. Fetch local dashboard HTML and extract the injected session token for local-only test calls.
2. For WebSocket/event feed, connect with headers like:
   - `Host: localhost:8765`
   - `Origin: https://nemo.andyylin.com`
   - `X-Forwarded-Host: nemo.andyylin.com`
   Confirm the WebSocket opens rather than logging an origin mismatch.
3. For HTTP Host-header behavior, compare:
   - `Host: nemo.andyylin.com` alone → should remain `400`.
   - `Host: nemo.andyylin.com` + `X-Forwarded-Host: nemo.andyylin.com` from loopback → should pass the Host guard.
4. Open the dashboard and confirm browser console has no plugin/WS errors.

Cloudflare Access allow-list note: allowed emails/groups live in Cloudflare Zero Trust Access policies, not in `/home/prodesign/.cloudflared/config.yml`. If PD One lacks Cloudflare API/origin-cert context, it can verify local tunnel/origin behavior but cannot authoritatively list allowed accounts. Use Andy's personal Hermes/Cloudflare account to inspect `Access → Applications → nemo.andyylin.com → Policies`; do not infer access from the local tunnel config. For this dashboard, prefer an explicit small allow-list such as Andy's personal account plus the Pro-Design admin account, not a broad company-domain allow.

## PD One Ops dashboard plugin MVP pattern

Hermes dashboard plugins are drop-in directories under the Hermes checkout/profile plugin path with:

```text
plugins/<name>/dashboard/manifest.json
plugins/<name>/dashboard/plugin_api.py
plugins/<name>/dashboard/dist/index.js
plugins/<name>/dashboard/dist/style.css
```

Manifest essentials:

```json
{
  "name": "pd-one-ops",
  "label": "PD One Ops",
  "description": "PD One operations catalog MVP",
  "icon": "ShieldCheck",
  "version": "0.1.0",
  "tab": { "path": "/pd-one-ops", "position": "after:cron" },
  "entry": "dist/index.js",
  "css": "dist/style.css",
  "api": "plugin_api.py"
}
```

Backend route files expose `router = APIRouter()` and are mounted at:

```text
/api/plugins/<name>/
```

Frontend bundles should use:

```js
const SDK = window.__HERMES_PLUGIN_SDK__;
const REG = window.__HERMES_PLUGINS__;
SDK.fetchJSON('/api/plugins/<name>/summary')
REG.register('<name>', Component)
```

Do not hand-read auth tokens in plugin JS; use the SDK fetch/WebSocket helpers so loopback-token and gated-cookie modes both work.

## PD One Ops data-safety rules

The first version should be read-only and should summarize operational metadata, not dump secrets or raw sensitive stores. Safe sources include:

- `/home/prodesign/.hermes/profiles/pdone/cron/jobs.json`
- `/home/prodesign/.hermes/profiles/pdone/supervisor/automations.json`
- `/home/prodesign/.hermes/profiles/pdone/skills/**/SKILL.md` frontmatter/description/path only
- `/home/prodesign/.hermes/profiles/pdone/policies/` file names/sizes only
- `/home/prodesign/.hermes/profiles/pdone/scripts/` file names/sizes only

Avoid displaying contents from policy-cache, sessions, logs, credentials, env files, auth stores, or company-sensitive raw data.

Good MVP tabs:

- Drift
- Cron
- Supervisor
- Skills

Good MVP drift checks:

- enabled cron job lacks supervisor/catalog entry;
- supervisor entry points to missing cron job;
- last delivery error is present;
- enabled prompt job has no attached skill/runbook.

## Verification receipts

Minimum verification before reporting success:

```bash
python -m py_compile plugins/pd-one-ops/dashboard/plugin_api.py
# import plugin_api.py and call summary(); assert ok and nonzero counts
# API: GET /api/dashboard/plugins includes pd-one-ops
# API: GET /api/plugins/pd-one-ops/summary returns ok/counts
# Static: /dashboard-plugins/pd-one-ops/dist/index.js returns JS and registers plugin
```

Browser verification:

- local dashboard route `/pd-one-ops?profile=pdone` renders KPI cards and tables;
- plugin nav shows `PD ONE OPS`;
- internal plugin tab buttons switch table content;
- browser console has no JS/plugin errors.

Cloudflare verification:

- unauthenticated `https://nemo.andyylin.com/pd-one-ops?profile=pdone` redirects to Cloudflare Access;
- authenticated user reaches the same rendered plugin page.

Commit/push Hermes source changes and run the configured Hermes backup helper after durable dashboard/plugin changes.
