# CAD/STEP attachment verification pitfall — 19LH-3 bucket thread

## Why this exists

In a Mattermost DFM/CAD review thread, PD One initially checked only the Hermes document cache and incorrectly reported that no 19LH-3 STP/STEP attachment was accessible. The file was later found in a staged working path and verified by STEP header/content. Future attachment-dependent replies should avoid that false negative.

## Durable workflow

When a user says a CAD file was uploaded, especially STP/STEP:

1. Start from the scoped Mattermost root thread: inspect the linked post, sibling posts, `file_ids`, `metadata.files`, and exact filenames when available.
2. Check Hermes profile document/image caches, but do **not** stop there.
3. Check relevant local staged/input paths created by prior processing for the same thread/task (for example project-specific work dirs under `/home/prodesign/.../input`).
4. Check OpenClaw inbound media cache for extensionless saved uploads.
5. For STP/STEP, identify files by content signature, not extension only:
   - `ISO-10303-21;`
   - `HEADER;`
   - `FILE_NAME(`
   - `FILE_SCHEMA (`
6. Before saying the file is available, produce a receipt: path, byte size, internal STEP filename, originating system/schema, and at least one parser or header verification result.
7. Before saying the file is unavailable, state exactly which scoped thread/cache/staged paths were checked.

## Example receipt format

- Path: `/path/to/file.stp` or extensionless inbound file
- Size: `N bytes`
- Internal name: value from `FILE_NAME`
- Source system: value from `originating_system`
- Schema: value from `FILE_SCHEMA`
- Basic geometry/parser receipt: entity counts, BREP counts, mesh/import status, or bounded header parse

## What not to save as a conclusion

Do not encode a durable claim that a CAD parser/tool is unavailable or broken based on one session. Environment setup changes. Save the verification pattern instead.
