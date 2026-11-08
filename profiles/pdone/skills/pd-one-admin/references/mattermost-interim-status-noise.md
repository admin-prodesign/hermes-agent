# Mattermost interim status / progress-bubble cleanup

Use this when Andy/admin asks why PD One posts interim step/status messages in Mattermost, why provider fallback/error breadcrumbs leak into channels, why temporary/progress/status bubbles remain after the final response, or to set Mattermost `tool_progress` to a named mode for a live test.

Examples:

- `⚠️ Non-retryable error (HTTP None) — trying fallback...`
- `❌ Non-retryable error (HTTP None): ...`
- `⚠️ 'NoneType' object is not iterable`
- progress/status posts that should disappear after the final answer but remain in the Mattermost thread/channel

## Scope and safety

- Treat quieting or cleanup of Mattermost gateway behavior as a gateway/config behavior change: get explicit admin approval before live config/code changes and restart only after a bounded check or approval.
- Mattermost group/channel replies still need bilingual EN + Traditional Chinese unless the channel policy says otherwise.
- Do not promise an adapter or gateway-code change is live until readback, targeted tests, an approved restart, and a post-restart check are complete. A `display.platforms.mattermost.tool_progress` leaf is different: the next Mattermost turn loads it. Do not restart for that leaf alone.
- Preserve PD One/OpenClaw custom patches before applying any upstream/branch fix. Inspect branch ancestry/diff first; do **not** blindly apply an old `fix/*` branch if it would roll back current `pd-one/custom-openclaw-patches` work.

## Fast diagnosis

1. Load `hermes-agent` for Hermes config/gateway command syntax, but do not edit bundled skills.
2. Confirm the customized checkout state before touching code:
   ```bash
   cd /home/prodesign/.hermes/hermes-agent
   git status --short --branch
   git branch --show-current
   git diff --stat
   git log --oneline --decorate -10
   ```
3. Read PD One profile config directly; do not use `~/.hermes/...` if the active process has a profile-specific `HOME` such as `/home/prodesign/.hermes/profiles/pdone/home`:
   ```bash
   python - <<'PY'
   import yaml
   p='/home/prodesign/.hermes/profiles/pdone/config.yaml'
   cfg=yaml.safe_load(open(p)) or {}
   display=cfg.get('display') or {}
   print({
       'interim_assistant_messages': display.get('interim_assistant_messages'),
       'mattermost': (display.get('platforms') or {}).get('mattermost'),
   })
   PY
   ```
   Redact secrets; only display non-secret display/progress settings.
4. Check the expected display settings:
   ```yaml
   display:
     interim_assistant_messages: false
     platforms:
       mattermost:
         tool_progress: off
         streaming: false
         cleanup_progress: true
   ```
5. Inspect current Hermes gateway code paths. As of the PD One customized Hermes checkout in May 2026, Mattermost support lives under the plugin path, not the old in-gateway path:
   - `gateway/display_config.py` resolves `display.platforms.<platform>.tool_progress`, `streaming`, and `cleanup_progress`.
   - `gateway/run.py::_prepare_gateway_status_message()` filters/sanitizes provider/status callbacks.
   - `gateway/run.py` finalization tracks temporary/progress message IDs and registers a post-final-delivery cleanup callback.
   - `gateway/platforms/base.py` defines generation-aware `register_post_delivery_callback(...)` and `pop_post_delivery_callback(...)`; verify callback invocation in the final-send path being exercised.
   - `plugins/platforms/mattermost/adapter.py` is the active Mattermost adapter and should contain `delete_message(...)` using Mattermost `DELETE posts/{id}`.
6. Search live logs for both logical cleanup and transport failures:
   ```bash
   grep -Ei 'Temp bubble|cleanup|MM API DELETE|Post-delivery cleanup|Connector is closed|Failed to create post' \
     /home/prodesign/.hermes/profiles/pdone/logs/gateway.log | tail -80
   ```
   A log such as `MM API DELETE posts/... network error: Connector is closed.` means the cleanup code is present and attempting deletion, but the Mattermost HTTP client/session was already closed when deletion ran.
7. Check active gateway processes and profile ownership. Duplicate runners can confuse which process owns the Mattermost websocket/session and which connector gets closed:
   ```bash
   pgrep -af 'gateway|hermes'
   ps -o pid,lstart,etime,args -p <pid1>,<pid2>
   ```
   In one observed case there were two runners from the same checkout: one `gateway run --replace` and one `--profile pdone gateway run --replace`.

## Interpretation pitfalls

- “Temp bubbles remain” does **not** automatically mean the custom patches were lost. First distinguish:
  1. config disables cleanup/progress suppression;
  2. cleanup callback never registered;
  3. callback registered but not popped/invoked on the final-send path;
  4. callback invoked but `delete_message` failed;
  5. delete failed because the Mattermost connector/session was closed during gateway replacement/shutdown;
  6. two gateway processes or stale generation ownership obscured which adapter performed send/delete.
- `cleanup_progress: true` is a post-delivery cleanup concern. The gateway intentionally defers deletion until after the final response is delivered so it does not remove progress feedback before the final answer is visible. A thread read after the final reply can look like progress never posted.
- Do not read YAML `tool_progress: false` as enabled or as an invalid key. The display normalizer maps boolean false and the tokens `false`, `0`, and `no` to `off` before the gateway decides whether to post bubbles.
- Do not treat global `display.tool_progress` as the Mattermost mode when `display.platforms.mattermost.tool_progress` is set. The platform leaf wins.
- `_cleanup_temp_bubbles()` may schedule async deletion and suppress per-message exceptions; rely on adapter logs and explicit debug logs rather than assuming failures will surface to the user.
- Old references to `gateway/platforms/mattermost.py` are stale for the pluginized checkout. Use `plugins/platforms/mattermost/adapter.py` unless inspecting historical commits.
- A large diff from an older cleanup branch to current `HEAD` is a safety warning. Prefer extracting the focused concept or writing a fresh patch on the current custom branch.

## Recommended fix pattern

- Config layer for normal chatter:
  ```yaml
  display:
    interim_assistant_messages: false
    platforms:
      mattermost:
        tool_progress: off
        streaming: false
        cleanup_progress: true
  ```
- Code layer for provider fallback/error breadcrumbs: extend the noisy-status/provider-error filter in `_prepare_gateway_status_message()` to include Mattermost, or use a platform-aware allowlist of platforms that should suppress these status callbacks.
- Code layer for temporary progress cleanup:
  - verify `MattermostAdapter.delete_message(channel_id, message_id)` calls Mattermost `DELETE posts/{id}` and reports success/failure;
  - ensure post-delivery cleanup is registered and invoked after every successful final delivery path, including streamed/suppressed-final cases if temp bubbles were created;
  - make deletion robust to closed connector/session where safe, or ensure cleanup runs before adapter teardown during replacement/shutdown;
  - add bounded debug logs for message-id tracking, callback registration/firing, delete result, and connector/session closed failures.
- Prefer a two-part fix: suppress/sanitize noisy provider breadcrumbs before posting, and delete legitimate temporary progress posts after final delivery.

## Set Mattermost tool_progress for a live test

Use this when Andy asks to set Mattermost tool progress to `off`, `new`, `all`, `verbose`, or `log` and watch the chat. The quiet default in this reference stays `off`. Do not change `cleanup_progress`, streaming, or the global mode unless asked.

1. Read `display.platforms.mattermost`, not only `display.tool_progress`. An explicit platform leaf wins. A global-only edit leaves Mattermost on its platform leaf.
2. Write a mode string. Never write YAML `false` for a named mode. The normalizer maps that boolean to `off`.
3. Copy `/home/prodesign/.hermes/profiles/pdone/config.yaml` to a timestamped file under that profile `backups/` directory before the write.
4. Set the leaf with the Hermes CLI. The patch tool cannot write this file. The CLI keeps comments:
   `hermes -p pdone config set display.platforms.mattermost.tool_progress <mode>`
   `off` is a CLI scalar word, so that command stores YAML `false`. After the write, if the raw Mattermost line is `tool_progress: false`, replace only that line with `tool_progress: "off"`. Do not leave the boolean.
5. Diff the backup against the live file. Accept the write only when that one leaf changed.
6. Resolve the effective mode from `/home/prodesign/.hermes/hermes-agent` with that checkout venv:
   `from gateway.display_config import resolve_tool_progress`
   Expect `(<mode>, True)`. A raw `config get` of `new` is not enough if a boolean still normalizes to `off`.
7. Do not restart the gateway. Each turn loads config through `_load_gateway_config()`, and the effective cache keys on the file signature. The in-flight reply still uses the old mode. The next Mattermost message is the test.
8. Tell the tester how to watch, or a correct change looks empty:
   - `new` emits a progress line only when the tool name changes. A repeat of the same tool is suppressed.
   - An unset `tool_progress_grouping` means `accumulate`: one bubble is edited in place.
   - `cleanup_progress: true` deletes those lines after a successful final reply. Watch the thread during the run.

## Verification checklist

- Config readback shows the Mattermost override, `cleanup_progress`, and global interim setting.
- Unit test or targeted probe confirms `_prepare_gateway_status_message(Platform.MATTERMOST, ..., noisy_provider_message)` returns `None` or a sanitized final-safe message according to the intended policy.
- Unit tests cover Mattermost post deletion success/failure and provider-noise filtering for status and final responses.
- Unit/integration tests cover post-delivery cleanup callback registration and invocation for the final-send path being fixed.
- Live smoke test in the target Mattermost thread: create a harmless temporary post through the adapter, send/verify a final response, verify the temporary post is deleted, and check logs for `send_success=True`, message id present, delete success, and no `Connector is closed` cleanup failure.
- Normal final answers still send to the correct Mattermost thread/root.
- For adapter or gateway-code changes, capture the restart receipt and post-restart health check. Get Andy/admin approval before restarting unless the gateway is already unresponsive under the standing exception. For a `tool_progress` leaf only, the receipt is the one-line config diff plus `resolve_tool_progress` returning `(<mode>, True)`. Do not restart.
- If opening an upstream Hermes PR, create the PR branch from the current upstream `main` commit (not an older local `origin/main` cache), cherry-pick only the focused fix, run targeted tests in that clean worktree, push, then verify PR `mergeable=MERGEABLE`.
- If durable Hermes/OpenClaw files changed, run the configured backup/commit helper when applicable.

## Targeted regression commands

Run narrow tests before broad suites when diagnosing cleanup/noise behavior:

```bash
cd /home/prodesign/.hermes/hermes-agent
python -m pytest \
  tests/gateway/test_mattermost.py::TestMattermostSend::test_delete_message_calls_api_delete \
  tests/gateway/test_mattermost.py::TestMattermostSend::test_delete_message_failure_returns_false \
  tests/gateway/test_telegram_noise_filter.py::test_mattermost_status_suppresses_retry_noise \
  tests/gateway/test_telegram_noise_filter.py::test_mattermost_final_response_sanitizes_raw_provider_errors \
  -q -o 'addopts='
```
