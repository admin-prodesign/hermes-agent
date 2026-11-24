# Approval routing versus reminder drift

Use this incident pattern when an approval runner keeps notifying a group that the authoritative form or authorized requester correction excludes.

## Recognition

- The form’s bounded routing block excludes a group, or the authorized submitter explicitly narrows/removes it.
- The bot acknowledges the correction, but the durable run still reports the old stage.
- A later scheduled pass emits the obsolete reminder again.

The durable state and emitted notification—not the acknowledgement text—show whether the correction took effect.

## Read-only diagnosis

1. Re-read the exact authoritative routing block; do not infer from signature rows or similarly named fields elsewhere in the document.
2. Inspect the run by stable root/source ID and record current stage, required groups, approvals, and stored reminder ID.
3. Compare the live stage with the authoritative route and the submitter’s authorized correction.
4. Classify a contradictory reminder as invalid. Tell excluded approvers not to act while preserving any human replies and original attachments.

## Safe correction envelope

A correction may require protected state, code, notification, or retention writes. Route a bounded admin handoff that names:

- the single run/root ID;
- the intended required/excluded groups;
- the exact runner/state/reminder targets allowed to change;
- preservation of human replies and source files;
- regression coverage preventing the stale stage from recreating the reminder;
- live state and notification readback as acceptance criteria.

Do not promise that a future scan will repair routing until the stage/group state has been read back. Do not delete reminders ad hoc when the runner has stored-post cleanup and reconciliation rules; use those rules so deletion remains idempotent and auditable.
