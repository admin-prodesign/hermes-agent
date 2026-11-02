# PD One Gog OAuth noVNC handoff

Use this when Andy/admin asks PD One to open a temporary browser/VNC session so they can approve additional Gog OAuth scopes interactively.

## Safety and scope rules

- Treat this as credential/config work. Require explicit approved-user authorization before generating a new OAuth consent link or changing stored tokens.
- Do not request Gmail scopes unless the user explicitly approves Gmail. For the common "everything we need, without Gmail" case, request Workspace operational scopes such as Drive, Docs, Sheets, Forms, Slides, Calendar, Contacts/People, Tasks, Sites, Meet, Apps Script, Drive Activity, and Drive Labels, but omit `gmail` services.
- Do not print token contents, client secrets, keyring passwords, cookies, or the final auth code. It is okay to provide the temporary noVNC password to the approved user for the handoff; rotate/cleanup afterward.
- CDP should remain host-local when possible; expose only noVNC/VNC ports externally for the user.

## Generate the Gog authorization URL

For PD One operational Google-file capabilities without Gmail:

```bash
SERVICES='calendar,drive,driveactivity,drivelabels,docs,slides,contacts,tasks,sheets,people,forms,sites,meet,appscript'
gog auth add admin@prodesign-group.com \
  --remote --step=1 \
  --services "$SERVICES" \
  --drive-scope full \
  --force-consent \
  --json --no-input
```

Verify before sharing:

- Parse the returned `auth_url`.
- Decode the `scope` parameter and confirm `gmail` is absent.
- Save the URL to a local temp/state file rather than pasting very long URLs repeatedly in chat.

## Temporary browser + noVNC pattern

If another VNC browser is already bound to `6080/5900/9222`, use alternate ports such as:

- noVNC: `6081 -> 6080`
- VNC: `5901 -> 5900`
- CDP: `127.0.0.1:9223 -> 9222`

Create the persistent-but-temporary browser profile under:

```text
/home/prodesign/.hermes/browser-profiles/gog-auth-pdone
```

Prefer writing a host start script first, then bind-mounting it into the container. Use an absolute host path for bind mounts; `$HOME` can resolve differently under profile/scheduler contexts and may accidentally create a directory at the container mount target.

Known-good start script shape:

```bash
#!/usr/bin/env bash
set -euo pipefail
: "${VNC_PASSWORD:?Set VNC_PASSWORD}"
DISPLAY_NUM="${DISPLAY_NUM:-99}"
GEOMETRY="${GEOMETRY:-1600x1000x24}"
export DISPLAY=":${DISPLAY_NUM}"
mkdir -p /data/chrome /tmp/.X11-unix
x11vnc -storepasswd "$VNC_PASSWORD" /tmp/vnc.pass >/dev/null
Xvfb "$DISPLAY" -screen 0 "$GEOMETRY" -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 0.8
openbox >/tmp/openbox.log 2>&1 &
/usr/lib/chromium/chromium \
  --no-sandbox \
  --disable-dev-shm-usage \
  --user-data-dir=/data/chrome \
  --remote-debugging-address=0.0.0.0 \
  --remote-debugging-port=9222 \
  --window-size=1500,900 \
  --no-first-run \
  --no-default-browser-check \
  --disable-background-timer-throttling \
  --disable-renderer-backgrounding \
  "${START_URL:-https://accounts.google.com/}" >/tmp/chromium.log 2>&1 &
x11vnc -display "$DISPLAY" -rfbauth /tmp/vnc.pass -forever -shared -listen 0.0.0.0 -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
websockify --web=/usr/share/novnc/ 0.0.0.0:6080 localhost:5900 >/tmp/novnc.log 2>&1 &
wait "$XVFB_PID"
```

Start the container using a unique name, alternate ports, and a local-only CDP binding:

```bash
docker rm -f pdone-gog-auth-browser >/dev/null 2>&1 || true
rm -f /home/prodesign/.hermes/browser-profiles/gog-auth-pdone/SingletonLock \
      /home/prodesign/.hermes/browser-profiles/gog-auth-pdone/SingletonSocket \
      /home/prodesign/.hermes/browser-profiles/gog-auth-pdone/SingletonCookie

docker run -d --name pdone-gog-auth-browser --restart unless-stopped \
  -p 6081:6080 -p 5901:5900 -p 127.0.0.1:9223:9222 \
  -e VNC_PASSWORD="$PASS" \
  -e START_URL="$AUTH_URL" \
  -e GEOMETRY='1600x1000x24' \
  -v /home/prodesign/.hermes/browser-profiles/gog-auth-pdone:/data/chrome \
  -v /home/prodesign/.hermes/browser-profiles/start-gog-auth-browser-vnc.sh:/tmp/start-gog-auth-browser-vnc.sh:ro \
  --entrypoint /bin/bash \
  pdone/browser-vnc:latest /tmp/start-gog-auth-browser-vnc.sh
```

## Verification before handoff

Run checks before posting credentials:

```bash
docker ps --filter name=pdone-gog-auth-browser --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
ss -ltnp | grep -E ':(6081|5901|9223)\b' || true
python3 - <<'PY'
import urllib.request
for url in ['http://127.0.0.1:6081/vnc.html', 'http://127.0.0.1:9223/json/version']:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            print('OK', url, r.status)
    except Exception as e:
            print('ERR', url, type(e).__name__, e)
PY
```

If CDP returns connection reset but the container logs show `DevTools listening` and noVNC is reachable, proceed with user login; CDP can be rechecked after the auth handoff.

## User handoff message

Provide:

- noVNC URL, preferably Tailscale IP, e.g. `http://100.x.y.z:6081/vnc.html`
- temporary VNC password
- a clear statement that requested scopes exclude Gmail
- instruction that after approval Google may redirect to `127.0.0.1:<port>` and fail to load; this is expected in the basic remote-flow handoff
- instruction to copy the entire final browser address-bar URL back into the thread so PD One can run `gog auth add ... --remote --step=2 --auth-url '<URL>'`

## Better noVNC pattern: complete the callback inside the browser

When the user asks to avoid copying the final `127.0.0.1` redirect URL, do not use `--remote --step=1/2`. Instead, run a normal listener on the host and bridge the container browser's loopback back to it:

1. Start `gog auth add` as a tracked background process, not `nohup`/shell background. Use a host listener reachable from Docker and keep Gmail out of scopes:

   ```bash
   SERVICES='calendar,drive,driveactivity,drivelabels,docs,slides,contacts,tasks,sheets,people,forms,sites,meet,appscript'
   EXTRA='https://www.googleapis.com/auth/admin.directory.group,https://www.googleapis.com/auth/admin.directory.group.member,https://www.googleapis.com/auth/apps.groups.settings'
   gog auth add admin@prodesign-group.com \
     --client prodesign-admin \
     --listen-addr 0.0.0.0:8766 \
     --services "$SERVICES" \
     --drive-scope full \
     --extra-scopes "$EXTRA" \
     --force-consent \
     --timeout 15m \
     --json
   ```

2. Capture the auth URL without relying on an auto-opened host browser. A safe pattern is to prepend a temporary fake `xdg-open` that writes its argument to a temp file, then run the same tracked background command. Avoid pipe-to-interpreter or heredoc parsing in user-facing command paths when possible.

3. Inside the noVNC container, proxy the browser's `127.0.0.1:8766` to the host listener, because Google's redirect URI is still `http://127.0.0.1:8766/oauth2/callback` from the browser's point of view:

   ```bash
   docker exec pdone-gog-auth-browser sh -lc 'python3 - <<"PY" >/tmp/port8766_proxy.log 2>&1 &
   import socket, threading, select
   LISTEN=("127.0.0.1",8766); TARGET=("172.17.0.1",8766)
   ls=socket.socket(); ls.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); ls.bind(LISTEN); ls.listen(20)
   print("proxy_listening", LISTEN, "to", TARGET, flush=True)
   def pipe(a,b):
       try:
           while True:
               r,_,_=select.select([a,b],[],[],300)
               if not r: break
               for s in r:
                   data=s.recv(65536)
                   if not data: return
                   (b if s is a else a).sendall(data)
       finally:
           for s in (a,b):
               try: s.close()
               except Exception: pass
   while True:
       c,addr=ls.accept(); t=socket.create_connection(TARGET,timeout=5)
       threading.Thread(target=pipe,args=(c,t),daemon=True).start()
   PY'
   ```

4. Open the captured auth URL in the noVNC Chromium. If Chrome's DevTools port is exposed only inside the container, invoke it from inside the container:

   ```bash
   docker cp /tmp/pdone_gog_live_auth_url.txt pdone-gog-auth-browser:/tmp/live_auth_url.txt
   docker exec pdone-gog-auth-browser sh -lc 'python3 - <<"PY"
   import urllib.request, urllib.parse
   url=open("/tmp/live_auth_url.txt").read().strip()
   urllib.request.urlopen(urllib.request.Request(
       "http://127.0.0.1:9222/json/new?"+urllib.parse.quote(url, safe=""),
       method="PUT"), timeout=5)
   PY'
   ```

5. After the user approves in the newest auth tab, poll the tracked Gog process. Success should complete automatically; no final URL paste is needed.

### noVNC “failed to connect to server” pitfall

If the noVNC page loads but clicking Connect says it failed to connect to the server, inspect `/tmp/x11vnc.log` inside the container. A common race is `XOpenDisplay(":99") failed` because `x11vnc` started before `Xvfb` was ready. Restart only `x11vnc` after `Xvfb` is up:

```bash
docker exec pdone-gog-auth-browser sh -lc 'pkill x11vnc || true; x11vnc -display :99 -rfbauth /tmp/vnc.pass -forever -shared -listen 0.0.0.0 -rfbport 5900 >/tmp/x11vnc.log 2>&1 &'
```

Verify from inside the container that port 5900 returns an RFB banner before asking the user to retry:

```bash
docker exec pdone-gog-auth-browser sh -lc 'python3 - <<"PY"
import socket
s=socket.create_connection(("127.0.0.1",5900),timeout=2)
print(s.recv(12))
s.close()
PY'
```

## Completing the OAuth exchange

Preferred UX when the user wants the auth to finish in noVNC instead of pasting a callback URL:

1. Start `gog auth add ...` in normal browser-listener mode with `--listen-addr 0.0.0.0:<port>` and the approved scopes.
2. If capturing the generated auth URL is needed without opening a host browser, temporarily prepend a tiny `xdg-open` shim that writes `$1` to a private temp file; do not print the URL in chat.
3. In the noVNC container, proxy the browser's loopback callback back to the host listener, e.g. `127.0.0.1:<port>` inside the container -> `172.17.0.1:<port>` on the host. A short Python socket proxy is sufficient when `socat` is unavailable.
4. Open the captured auth URL in the noVNC Chromium through its in-container DevTools endpoint (`http://127.0.0.1:9222/json/new?...`) or by pasting it manually. After approval, Google's redirect to `127.0.0.1:<port>/oauth2/callback` should hit the container proxy and complete Gog automatically.
5. Verify the background `gog auth add` process reports `Authorization received. Finishing…` and `stored: true`, then export/delete a temporary token only long enough to verify expected scopes and that Gmail scopes remain absent.

Pitfall: noVNC can load while the internal VNC server is not connected. If the page says "failed to connect to server" and websockify logs show `Failed to connect to localhost:5900`, restart `x11vnc` inside the container after Xvfb is up, then verify TCP `5900` returns an `RFB 003.008` banner before handing the URL back to the user.

Fallback path after the user pastes back the final `127.0.0.1:<port>/oauth2/callback?...code=...&state=...` URL:

```bash
gog auth add admin@prodesign-group.com \
  --remote --step=2 \
  --auth-url "$PASTED_REDIRECT_URL" \
  --json --no-input
```

### Fallback: `manual auth state mismatch`

If `--remote --step=2` fails with:

```text
manual auth state mismatch; run remote step 1 again
```

but the profile config directory still has a matching pending state file, complete the exchange through the interactive/manual path by piping the pasted redirect URL into `gog auth add --manual`. Use the same account, client, services, drive scope, and force-consent settings that generated the URL:

```bash
printf '%s\n' "$PASTED_REDIRECT_URL" | gog auth add admin@prodesign-group.com \
  --client prodesign-admin \
  --manual \
  --services calendar,drive,driveactivity,drivelabels,docs,slides,contacts,tasks,sheets,people,forms,sites,meet,appscript \
  --drive-scope full \
  --force-consent \
  --json
```

Do not echo the pasted URL back in logs or chat; redact `code=` and any token-like fields in command output.

## Cleanup

- Schedule cleanup for the temporary container, e.g. a one-shot cron/no-agent job within 2 hours that runs `docker rm -f pdone-gog-auth-browser`.
- After successful token exchange, verify with `gog auth doctor --json --no-input`, `gog auth list --json --no-input`, and a read-only operation for the newly authorized services. Capture JSON to temp files before parsing with Python/JQ rather than piping `gog` directly into an interpreter.
- Confirm Gmail scopes remain absent and that the OpenClaw/Gog wrapper still blocks Gmail send unless separately approved. A bounded smoke test is `gog gmail send --help`; in PD One it should exit with the wrapper block message unless `GOG_ALLOW_GMAIL_SEND=1` was deliberately set after approval.
