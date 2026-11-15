# Google Groups OAuth via noVNC with in-browser callback

Use this when Andy/admin needs to add Google Workspace/Groups scopes to the `admin@prodesign-group.com` Gog OAuth token and wants the flow to complete inside a temporary noVNC browser instead of pasting a final `127.0.0.1` redirect URL.

## Scopes for Google Groups administration

For creating Google Groups, adding members, and reading/copying group settings, request these extra user OAuth scopes in addition to the normal non-Gmail operational scopes:

```text
https://www.googleapis.com/auth/admin.directory.group
https://www.googleapis.com/auth/admin.directory.group.member
https://www.googleapis.com/auth/apps.groups.settings
```

Keep Gmail out unless separately approved.

## Pitfall: Docker browser `127.0.0.1` is not the host

If the noVNC browser runs inside Docker and Gog listens on the host, a Google redirect to:

```text
http://127.0.0.1:<port>/oauth2/callback?code=...&state=...
```

will target the browser container, not the host Gog listener. The user will see a localhost callback page/error or have to copy the URL manually.

Preferred fix: run the Gog listener on a host port bound to all interfaces and add a tiny loopback proxy inside the noVNC container from `127.0.0.1:<port>` to the Docker host bridge address.

## In-browser callback pattern

1. Start the Gog auth listener on the host with an explicit callback port, e.g. `8766`:

```bash
SERVICES='calendar,drive,driveactivity,drivelabels,docs,slides,contacts,tasks,sheets,people,forms,sites,meet,appscript'
EXTRA='https://www.googleapis.com/auth/admin.directory.group,https://www.googleapis.com/auth/admin.directory.group.member,https://www.googleapis.com/auth/apps.groups.settings'
PATH=/tmp/pdone-fake-browser:$PATH gog auth add admin@prodesign-group.com \
  --client prodesign-admin \
  --listen-addr 0.0.0.0:8766 \
  --services "$SERVICES" \
  --drive-scope full \
  --extra-scopes "$EXTRA" \
  --force-consent \
  --timeout 15m \
  --json
```

2. If needed, create a fake `xdg-open` first so the auth URL is captured to a file rather than trying to open a local browser on the host:

```bash
mkdir -p /tmp/pdone-fake-browser
cat > /tmp/pdone-fake-browser/xdg-open <<'SH'
#!/usr/bin/env sh
printf '%s\n' "$1" > /tmp/pdone_gog_live_auth_url.txt
exit 0
SH
chmod +x /tmp/pdone-fake-browser/xdg-open
```

3. Inside the noVNC browser container, proxy the browser's localhost callback to the host listener. On Docker bridge setups, `172.17.0.1` is usually the host gateway; verify if needed.

```bash
docker exec pdone-gog-auth-browser sh -lc 'python3 - <<"PY" >/tmp/port8766_proxy.log 2>&1 &
import socket, threading, select
LISTEN=("127.0.0.1",8766)
TARGET=("172.17.0.1",8766)
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
    c,addr=ls.accept()
    try:
        t=socket.create_connection(TARGET,timeout=5)
    except Exception:
        c.close(); continue
    threading.Thread(target=pipe,args=(c,t),daemon=True).start()
PY'
```

4. Open the captured auth URL in the noVNC Chromium using the container-local Chrome DevTools endpoint, so the user just clicks through the newest tab:

```bash
docker cp /tmp/pdone_gog_live_auth_url.txt pdone-gog-auth-browser:/tmp/live_auth_url.txt
docker exec pdone-gog-auth-browser sh -lc 'python3 - <<"PY"
import urllib.request, urllib.parse, json
url=open("/tmp/live_auth_url.txt").read().strip()
base="http://127.0.0.1:9222"
req=urllib.request.Request(base+"/json/new?"+urllib.parse.quote(url, safe=""), method="PUT")
r=urllib.request.urlopen(req, timeout=5)
print("new_tab", r.status)
PY'
```

5. After approval, Gog should print `Authorization received. Finishing…` and store the token. Verify by exporting only to a private temp file, checking scopes, and deleting the export immediately. Confirm Gmail is absent.

## noVNC/VNC startup pitfall

If noVNC loads but says `failed to connect to server`, check the container's `/tmp/x11vnc.log`. `x11vnc` may have started before Xvfb was ready and failed with `XOpenDisplay` errors. Restart x11vnc inside the container after Xvfb is running:

```bash
docker exec pdone-gog-auth-browser sh -lc 'pkill x11vnc || true; x11vnc -display :99 -rfbauth /tmp/vnc.pass -forever -shared -listen 0.0.0.0 -rfbport 5900 >/tmp/x11vnc.log 2>&1 &'
```

Verify the VNC TCP greeting inside the container:

```bash
docker exec pdone-gog-auth-browser sh -lc 'python3 - <<"PY"
import socket
s=socket.socket(); s.settimeout(2); s.connect(("127.0.0.1",5900)); print(s.recv(12)); s.close()
PY'
```

Expected prefix: `RFB 003.008`.
