# AppSheet stable promotion with admin profile

Use when a Pro-Design AppSheet latest/editor definition has been saved and needs to become production/stable.

## Pitfall

The default/OpenClaw AppSheet cookie profile may successfully call `/api/saveapp` but fail stable promotion with:

```text
This feature is only available as part of an Enterprise plan
```

In this workspace that error can be misleading. Do not report promotion blocked until retrying with the admin/tailscale-login profile for `admin@prodesign-group.com`.

A `401` from tailscale-login is a different failure: that cookie jar is stale. Do not treat it as the Enterprise-plan error, and do not stop. Retry `SetStableVersion` with the editor cookie profile that can already `GET /api/loadApp`. A `Success: true` from that profile is a real promotion response; still prove it by loading the stable version.

## Correct cookie profile

```text
/home/prodesign/.hermes/profiles/pdone/legacy-openclaw/workspace/browser-profiles/tailscale-login/Default/Cookies
```

Use this cookie jar for stable promotion requests.

## Promotion request

Endpoint:

```text
POST https://www.appsheet.com/Manage/SetStableVersion
```

Form fields:

```text
appId=<app id>
version=<latest Version from /api/loadApp>
percentOnLatestVersion=0
```

Headers:

```text
X-Requested-With: XMLHttpRequest
Origin: https://www.appsheet.com
Referer: https://www.appsheet.com/template/appdef?appId=<app id>
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
```

Expected response:

```json
{"Success": true, "ErrorDescription": ""}
```

## Verification checklist

1. Fresh load latest:
   ```text
   /api/loadApp/<appName-or-appId>?version=&checkConsistency=true&useUpdatedWarningText=false
   ```
2. Confirm latest is safe:
   ```text
   IsValid == true
   IsRunnable == true
   IsDeployable == true
   ```
3. Promote latest `Version` with the admin profile.
4. Fresh load again and confirm:
   ```text
   StableVersion == target_version
   ```
5. Load the stable version explicitly:
   ```text
   /api/loadApp/<appName-or-appId>?version=<StableVersion>&checkConsistency=true&useUpdatedWarningText=false
   ```
6. Verify the business change in the stable object itself, not just `StableVersion` metadata.

## Reporting rule

Do not say “promoted” unless the post-promotion readback proves the stable version contains the intended change. If latest advances after promotion, `Version` may be greater than `StableVersion`; the key proof is that `StableVersion` equals the promoted target and the stable-version object contains the fix.

An unversioned `/api/loadApp` can keep a stale `StableVersion` for a short time after `SetStableVersion` returns `Success: true`. Load the named target version as well. If that object contains the change and a later unversioned load shows `StableVersion` equal to the target, the promotion is proven. Do not post a second definition save only because the first readback lagged.
