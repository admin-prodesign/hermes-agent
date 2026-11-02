# PDAPP decide vs Mattermost mention auto-translation

Use when an `admin: approve/reject PDAPP-...` appears to fail, when Hermes dangerous-command `/approve`/`/deny` is ignored in Mattermost, or auto-translation must not rewrite commands.

## Diagnose the exact permalink

Dry-run `pd_one_admin_approval_decide` against the linked post id. A bot failure notice is not a decision post.

| `blocked_reason` | Meaning |
|---|---|
| `not_authorized_sender` | Author is not Andy. `pdone` replies cannot decide. |
| `edited_message_without_existing_decision` | Unrecorded edit outside an allowed envelope. |
| `ticket_not_pending:<status>` | Parser accepted the post; ledger status blocks a new decide. |
| `no_strict_decision` | Body is not one standalone command (`/queue `, extra tickets, or prose). |

If the ticket is already `in_progress`, do not collect another `admin: approve`.

## Hermes dangerous-command `/approve` is a different gate

Protected agent-instruction writes (`AGENTS.md` and siblings) block on the Hermes pending-command prompt, not a PDAPP ticket. Chat prose such as “I approve the change” is not `/approve`. After that prompt times out, do not retry the write through terminal, `execute_code`, or another path — silence is not consent.

While the yellow prompt is pending, the only Mattermost replies that resolve it are a **standalone** `/approve`, `/deny`, or an exact plaintext token (`yes`, `approve`, `ok`). A bilingual-autoedit envelope is not a slash command: the client wraps the post as a `中文` body, an `English` body, then `<!-- bilingual-autoedit:v1 -->`, so `/approve` never starts the inbound text and never matches the exact-word busy handler. Recover the English (else Chinese) section before command detection; skip mention-translation and Andy-mention collect for slash lines and `admin:` / `管理員：` lines. Collect-script skips are live on the next collect run; adapter unwrap/skip is not active until an approved pdone recycle.

## Allowed unrecorded-edit envelopes

- `bilingual-autoedit:v1` PDAPP form: `管理員：核准 PDAPP-...` / `admin: approve PDAPP-...` / `<!-- bilingual-autoedit:v1 -->`.
- `bilingual-autoedit:v1` labeled form: a `中文` body, an `English` body, then the marker. For slash/admin commands, treat the English section as the command.
- `mention-translation:v1`: original one-line command, then `---`, then `**Translation / 翻譯 (utility-agent):**`. Parse the original command only. Ignore a trailing `@pdone`. Unrelated edits still fail closed.

## Built vs active

- Listener/MCP (`tools/pd_one_admin_approval_listener.py`) can accept the mention-translation envelope on the next decide dry-run without a gateway restart.
- Andy-mention collect (`scripts/mattermost_andy_mention_translate_collect.py`) skips slash and `admin:` / `管理員：` commands on the next collect run.
- Adapter unwrap/skip (`_inbound_command_text`, `_looks_like_command_message`) is not live until an approved PD One gateway restart.

Report built / verified / active separately.
