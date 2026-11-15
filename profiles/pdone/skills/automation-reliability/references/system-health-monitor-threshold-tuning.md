# System health monitor threshold tuning

Use this when reviewing or tuning host/system health watchdogs that alert on Linux PSI, load, memory, swap, IO, or disk conditions.

## Durable lesson

PSI metrics are valuable but noisy when used as standalone chat-alert triggers. A low memory PSI threshold can fire during IO-heavy reclaim/writeback workloads even when `MemAvailable` is still healthy. Preserve the signal, but gate it by severity or supporting evidence.

## Recommended pattern

1. Keep hard resource exhaustion signals as independent alerts:
   - available memory below a low threshold (for example `<= 15%`)
   - disk space/inodes below operational safety thresholds
   - sustained CPU PSI/load above a clear host-capacity threshold
2. Treat moderate memory PSI as diagnostic unless it is paired with other pressure:
   - severe standalone memory PSI can alert directly (example: `avg300 >= 15%`)
   - composite memory PSI can alert only when memory PSI is elevated and IO PSI plus swap pressure are also elevated (example: memory PSI `>= 10%`, IO PSI `>= 20%`, swap used `>= 40%`)
3. Include context in the alert body so it is actionable:
   - CPU PSI, IO PSI, memory PSI
   - available memory
   - swap used GiB/percent
   - top culprit process or IO writer when practical
4. Validate with a dry-run/no-agent cron equivalent before reporting completion:
   - syntax check the monitor script
   - run one normal dry-run expecting no alert if current state is healthy
   - run a forced snapshot/format dry-run if available to verify alert content
5. Avoid gateway restarts for threshold-only changes unless the monitor depends on the gateway process itself and Andy explicitly approves a restart.

## Pitfall

Do not lower alert noise by deleting PSI checks entirely. PSI can catch real user-visible stalls before memory is exhausted; the durable fix is to make PSI thresholds severity-tiered/composite and improve alert evidence.
