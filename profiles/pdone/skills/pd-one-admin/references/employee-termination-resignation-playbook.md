# Employee termination / resignation access cleanup playbook

This file is **access cleanup only**. If Andy/HR asked to start the Mattermost 離職程序 playbook, use `mattermost-playbooks` → `references/employee-termination-thread-runner.md` instead.

Use when Andy/admin asks PD One to process or audit employee termination, resignation, departure, or offboarding access cleanup. A live termination playbook start already tries T10 and T12. Do not run a second remove in the same start unless the script receipt says the readback failed.

## Safety and approval

- Treat this as HR/admin-sensitive and access-destructive work.
- Use exact employee identity evidence: name + email and, when available, `PersonID` / employee ID from the HR/AppSheet source of truth.
- For employee-facing Mattermost requests, enforce PD One permission policy before disclosing or changing anything.
- Make a read-only audit first when practical. Execute removals only after explicit Andy/admin approval for the named employee/email and bounded systems.
- Report concise machine-verifiable receipts: system, object/group/app, before state, action response, and after readback.

## Required access-removal checklist

For a termination or resignation offboarding run, include these checks/removals unless Andy explicitly scopes them out:

1. **AppSheet app subscriber/share list**
   - Load `appsheet-copilot` → `references/appsheet-user-access-offboarding.md`.
   - Inspect `GET https://www.appsheet.com/api/loadUsers/<app_id>`.
   - If approved, remove the named email with `POST https://www.appsheet.com/manage/RemoveAppSubscriber`.
   - Verify by reloading `/api/loadUsers/<app_id>` and requiring the email to be absent; report before/after subscriber counts.
   - Do not mark checklist T10 complete from blank `HR_Employees` role fields or a missing `HR_Employees_AppSheet_Settings` row. Those are not the subscriber list. Leave T10 pending when the `loadUsers` readback did not run. Andy saying T10 is done is not that readback. List first. If `present` is false, mark T10 complete and do not call remove. If `present` is true, do not mark T10 complete from the words alone.
   - Resolve the person with the table probe on `env=deployed`. A Chinese name is not a PersonID. Probe `FILTER(HR_Employees, [Employee ID] = "...")` or `FILTER(HR_Employees, [Name_ZH] = "...")`, then confirm with `FILTER(HR_Employees, [PersonID] = "<live PersonID>")`. The live PersonID is often a short AppSheet code, not a `P-` id. A bare employee number, a bare PersonID, or the default prototype env returns 0 rows and is not "person not found."
   - `pd_one_appsheet_user_access.py` adds a subscriber and only authorizes the new-employee channel and PD One Admin. It is not `RemoveAppSubscriber`. Do not call it to complete T10. For T10 use `python3 /home/prodesign/.hermes/profiles/pdone/tools/pd_one_appsheet_subscriber_ops.py list --email <email>`, then `remove --email <email> --mm-post-id <Andy post id>` (preview by default; live needs `--live --confirm-live-write 'RUN LIVE APPSHEET SUBSCRIBER REMOVE'`). The tool re-fetches Andy's post and reads back the subscriber list. Pass Andy's post id, not the bot checklist post id. The check reads only that post and its thread root, so an email printed only on the checklist does not authorize remove. If that check denies and `present` is true, do not open a PDAPP ticket and do not POST `RemoveAppSubscriber` by hand. Report the deny and leave T10 pending.

2. **AppSheet table-driven access fields**
   - Check departed employee rows in `HR_Employees` and canonical `HR_Employees_AppSheet_Settings` by `PersonID`.
   - Look for AppSheet email/roles/views/navigation/menu/notification/team-members access fields.
   - Clear only after separate bounded approval and row-API readback; do not assume share-list removal clears table-driven access. A termination-thread request to remove someone from AppSheet is T10, the subscriber list. It does not authorize a patch of `HR_Employees` roles, notification groups, or Employment Status.

3. **Google Groups**
   - There is no `google-groups-offboarding.md`. Use `gog admin groups list --domain prodesign-group.com --account admin@prodesign-group.com --json --no-input --all` and `gog admin groups members list <groupEmail> --all --json --account admin@prodesign-group.com --no-input`.
   - A `gog` exit 8 or `dial tcp ...:443: i/o timeout` to `*.googleapis.com` is not a closed T12 blocker. Load `google-hosts-pin-heal` and run that pin once, then retry the Directory call once. Stop only when that skill returns `FAIL no working Google IP`. The same timeout also blocks the termination Sheet write; do not mark T10 or T12 complete until the Sheet `status` readback succeeds.
   - For Andy, scan every Directory group in one shell `for` over the emails from `groups list`. Count the exact email with `grep -c`. Do not put `python -c` in that loop: the card guard matches `python -c` inside the command even when the outer command is an ordinary `for`. Do not batch `pd_one_google_group_members`: that local tool accepts one call, and a same-turn fan-out of those calls can time out the group you just changed. Remove only groups whose live count is greater than 0. A portal-cache hit on a group whose live count is 0 is stale. Do not remove that group.
   - Permissions follow the exact sender, not the room. For Andy's own request, ordinary shell (including `gog admin groups members list/remove`) and typed tools are allowed in any room, including the termination room. Only a command that would post an approval card (`python3 -c`, heredoc, `bash -c`, `systemctl`, and similar) is blocked outside PD One Admin and DMs. Employee senders never get `terminal`. Without shell, get the domain group list from `pd_one_google_group_owner_enforcement` with `operation=ensure_owners` and `dry_run=true`. That call does not write. Unique `plan[].group` values are the Directory group list. Then call `pd_one_google_group_members` with `filter_email` set to the company email on every returned group. A portal-cache miss, or a direct `all-company@` count of 0, is not that scan.
   - If every filtered count is 0, no live remove is required. Do not refresh the portal cache when no membership changed. The tracker may mark T12 complete only after that full scan.
   - If any filtered count is greater than 0, remove each hit, then rescan every Directory group before marking T12 complete. For Andy's request, use `gog admin groups members remove <groupEmail> <memberEmail> --account admin@prodesign-group.com --no-input --force --json`. `--force` is required with `--no-input`; without it the CLI waits for a confirmation and fails closed. Do not pass `mm-post:<id>` as the MCP `pd_one_google_group_change_apply` `ticket_id`. That wrapper still requires `PDAPP-YYYYMMDD-XXXXXXXX` and rejects the prefix before the script runs. The script flag is `--mm-post-id` on `pd_one_google_group_member_ops.py` with `--live` and `--confirm-live-write 'RUN LIVE GOOGLE GROUP MEMBER CHANGE'`. That check reads only the authorizing post and its thread root, and the required term is the full email, not a local-part prefix and not a later reply in the thread. If that check denies, do not open a PDAPP ticket and do not stop. Use the `gog` command above. `removed: true` is not absence. Read that group back with one `gog admin groups members list` before any other Directory call or the portal refresh. A same-turn fan-out of member lists plus the refresh times out the group you just changed. Then read back each removed group with `pd_one_google_group_members` only if that single list already shows the email absent. Do not mark T12 complete, and do not invent a browser click path, until a full Directory member-list readback shows 0. Do not use a subagent shell. If a step is still blocked after the hosts-pin heal, quote the tool result, leave T12 pending, and do not refresh the portal cache. Name a group as a current member only when this turn's Directory list returned that hit. A portal-cache or expanded-membership hit is an unverified hint, not a remove target and not proof the person is still a member.
   - If Andy names one group, remove only that group. Do not expand to every membership. "Remove her from Google Groups" with no group name is the full domain scan, not one group. A short local-part such as `yang@` still means that company email after the HR row resolves it. It does not authorize a prefix match inside the post-auth check.
   - A live Directory removal does not update portal ACL. Refresh with `/usr/bin/python3 /home/prodesign/apps/pd-one-portal/scripts/refresh_pd_one_google_group_members.py` (the systemd unit interpreter, not PATH `python3`), then require the email absent from `policy-cache/portal/google-group-members.json`. A content search of that file with 0 matches is the readback. The portal reloads that file on mtime. Do not restart it for the refresh. Say this receipt proves only the portal group cache, not Mattermost chat access.
   - Expanded `all-company@` can list someone only because a nested department group contained them. A direct all-company lookup of 0 does not prove the expanded cache is clean. Trust the refreshed portal cache.

## Optional / context-dependent systems

Add these when relevant to the employee’s role or Andy’s scope:

- Google Drive/Docs/Sheets ownership or sharing cleanup.
- Mattermost account/channel/team access.
- AppSheet source data ownership or bot/workflow ownership.
- Shared credentials, device accounts, VPN/Tailscale, Windows/domain accounts, email aliases, calendars, and external SaaS access.
- Company social page-manager roles. Follow the section below; do not fold them into Google Groups.

## Company social page-manager removal

Use only when Andy/admin names social platforms for one employee: YouTube, Facebook, Instagram, TikTok, LinkedIn, Google Business Profile, or any other company page where that person might have manager access. This is not the 離職程序 checklist and not the required AppSheet / Google Groups checklist.

1. Resolve the exact identity from HR (`Name_ZH`, `Name_EN`, `Company Email` or `Appsheet Email`, `PersonID`). `Employment Status` still `Employed` does not block a scoped social removal and does not authorize any other system.
2. Do not remove department Google Groups, suspend the Workspace user, or start 離職程序 unless those were explicitly in scope. A department group is not a page role.
3. Do not treat these tools as page-admin ACL: `social-platform-operations` is post/read/DM only; `gog youtube` is the YouTube Data API (search, videos, playlists, comments, channel list) and has no manager-remove command; `gog maps` is Places, directions, and geocode, not Business Profile managers and not review deletion.
4. Do not ask for or accept a password in chat. If no page-owner admin session can list roles, stop. Report each named platform as not removed, and say a vault-saved page-owner login or an interactive admin console is required. Do not invent a click path.
5. When Andy asks PD One to get access, do not offer Google OAuth scope expansion. `youtube` or `business.manage` on `admin@prodesign-group.com` still acts only for an account that is already an owner of that channel or Business Profile. A 403 or missing scope is not fixed by a new consent screen. Facebook, Instagram, TikTok, and LinkedIn have no company admin API here.
6. Do not open a login page until Andy picks the handoff and confirms he controls a remaining page-owner login. Vault: open that platform's official login page, call `browser_vault_save_login`, type only the identifier, let the vault fill the password, and use `browser_vault_enter_code` for 2FA. noVNC: the permanent PD One desktop is `https://nemo.tail05d15a.ts.net/pdone-desktop/vnc.html?path=pdone-desktop/websockify&autoconnect=1` (container `pdone-desktop-browser`, Tailscale path `/pdone-desktop` → `127.0.0.1:6083`). Andy logs in himself. Operate only after he says the member list is visible. Do not reuse Looker noVNC, raw `:6081`, or `pdone-gog-auth-browser`. Do not put the VNC password in the skill or memory. If he asks for a bookmark, this noVNC build reads `password` from the query string; give that URL only in a 1:1 admin DM. That Chromium has no screen lock, D-Bus session, Bluetooth, or security key, and remote debugging is on, so it refuses passkeys. Tell him to use Try another way. Do not add a virtual authenticator. If he does not already control a remaining owner login, stop. Do not recover or reset that login.
7. A personal review or post is not manager access. Do not treat deleting that content as the access removal.
8. Never claim a role was removed without a readback of that platform's member/role list showing the named identity absent. Omit phone, license plate, and other HR fields that are not the access key.
9. Company YouTube managers are Google Brand Account managers, not a `gog youtube` ACL. `admin@prodesign-group.com` is the owner of brand account `115430276833119994289`. The owner manages people at `https://myaccount.google.com/brandaccounts/115430276833119994289/view` with no query string. If Andy pastes that page with a `rapt=` parameter, do not open, fetch, store, or repeat the URL. `rapt` is a Google reauth token. Record only the brand account id. An owner saying they removed someone is `reported removed, not verified` until a page-owner session readback shows the named identity absent. That page does not cover Facebook, Instagram, TikTok, LinkedIn, or Google Business Profile.
10. A personal email Andy names is a second access key, alongside the company email. Match both. "I am removing it" is in progress, not removed. Do not store that personal address in memory or this playbook. Confirm both addresses are absent before recording the platform as reported removed.
11. Cite the official console instead of inventing a menu. Facebook posting rights are the Content task. Portfolio people: Meta Business Suite Settings, Pages under Profiles or Accounts, then People. Full control can remove other owners and delete the page. Who published a post is **Published by** on the post, or Publishing Tools → Published Posts. Page Management history lists access changes, not posts. Instagram portfolio people have no separate public URL: `https://business.facebook.com/latest/settings`, then the Instagram account under Accounts or People, Manage, Remove access. Google Business Profile: `https://business.google.com/`, then More → Business Profile settings → People and access. Only an owner can remove a person, and removal does not delete reviews.
12. To save a public Maps contributor profile, resolve the short link, then open `https://www.google.com/maps/contrib/<id>/reviews`. The unsuffixed contrib URL opens Photos. Save a screenshot plus the visible name, level, counts, and each company card's stars and text. A star-only card may have no text. Do not delete the review.

For a social-only request, do not use the full offboarding receipt. List each named platform as removed, not present, or not removed, with the readback or the missing admin path.

## PD One portal and Mattermost revocation

Removing a department Google Group does not by itself revoke PD One chat access. Do both layers, and say which one each receipt proves.

1. Group removal and portal cache refresh are the portal layer. Follow the Google Groups checklist above. Require the email absent from the refreshed portal cache before saying portal access is gone.
2. Mattermost PD One access is the exact-id allow-list. Set that user's `status` to `inactive` in canonical `policies/mattermost-users.json`. From the pdone profile root, run `python3 tools/mattermost_policy_lookup.py generate-cache`, then `python3 tools/mattermost_policy_lookup.py lookup <id>`. Require `active=false`, `decision=inactive_user`, and `dmEnabled=false`.
3. Do not delete the Mattermost user or remove channel membership unless Andy asked for that separately. Inactive only stops PD One scoped work.
4. Do not restart the gateway for this cache change. A stale document-access blob may still name the old group; inactive denies scoped tools anyway. Do not treat that blob as live Drive ACL.

## Output pattern

Keep the admin chat receipt short:

```text
Offboarding cleanup for <email>:
- AppSheet subscriber list: removed / not present / not checked; receipt
- AppSheet table-driven access: cleared / still present / not in scope; receipt
- Google Groups: removed from N groups; final scan 0 remaining matches
- Exceptions: <none or list>
```
