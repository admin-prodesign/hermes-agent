"""PD One wiki-candidate tools for Hermes.

These tools let the PD One Hermes profile emit structured company-wiki update
candidates without giving employee-facing sessions direct access to canonical
wiki files. Hermes/PD Neo intake jobs validate and route the candidates.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.registry import registry, tool_error, tool_result

SCRIPT = Path("/home/prodesign/.hermes/scripts/pd_one_wiki_candidate_emit.py")

ENTITY_TYPES = {"mold", "equipment", "customer", "process", "source-system", "other"}
UPDATE_TYPES = {"observation", "correction", "resolution", "maintenance", "customer-preference", "open-question", "source-link"}
SENSITIVITIES = {"normal", "internal", "confidential", "restricted"}
RISKS = {"low", "review_required", "sensitive", "reject"}
ACTIONS = {"auto_apply", "review", "quarantine", "reject"}


def _check_reqs() -> bool:
    return SCRIPT.exists()


def _listify(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def emit_wiki_update_candidate(
    entity_type: str,
    entity_id: str,
    entity_display_name: str,
    update_type: str,
    detail: Any,
    source_channel_id: str,
    source_post_id: str = "",
    source_thread_id: str = "",
    message_ref: Any = None,
    domain: str = "general",
    risk: str = "review_required",
    sensitivity: str = "internal",
    recommended_action: str = "review",
    summary_zh_tw: str = "",
    summary_en: str = "",
    suggested_section: str = "Recent observations / 最近觀察",
    excerpt: str = "",
    agent: str = "employee-assistant",
    dry_run: bool = False,
    task_id: str | None = None,
) -> str:
    """Emit a structured wiki-update candidate from PD One into Hermes intake."""

    if not SCRIPT.exists():
        return tool_error(f"PD One wiki candidate emitter is not installed at {SCRIPT}")
    if entity_type not in ENTITY_TYPES:
        return tool_error(f"entity_type must be one of {sorted(ENTITY_TYPES)}")
    if update_type not in UPDATE_TYPES:
        return tool_error(f"update_type must be one of {sorted(UPDATE_TYPES)}")
    if risk not in RISKS:
        return tool_error(f"risk must be one of {sorted(RISKS)}")
    if sensitivity not in SENSITIVITIES:
        return tool_error(f"sensitivity must be one of {sorted(SENSITIVITIES)}")
    if recommended_action not in ACTIONS:
        return tool_error(f"recommended_action must be one of {sorted(ACTIONS)}")
    details = _listify(detail)[:5]
    if not details:
        return tool_error("detail is required and must contain at least one non-empty item")

    cmd = [
        sys.executable,
        str(SCRIPT),
        "--entity-type", entity_type,
        "--entity-id", str(entity_id),
        "--entity-display-name", str(entity_display_name),
        "--update-type", update_type,
        "--source-channel-id", str(source_channel_id),
        "--domain", str(domain),
        "--risk", risk,
        "--sensitivity", sensitivity,
        "--recommended-action", recommended_action,
        "--suggested-section", str(suggested_section),
        "--agent", str(agent),
    ]
    for flag, value in (
        ("--source-post-id", source_post_id),
        ("--source-thread-id", source_thread_id),
        ("--summary-zh-tw", summary_zh_tw),
        ("--summary-en", summary_en),
        ("--excerpt", excerpt),
    ):
        if str(value or "").strip():
            cmd.extend([flag, str(value)])
    for item in details:
        cmd.extend(["--detail", item])
    for item in _listify(message_ref)[:10]:
        cmd.extend(["--message-ref", item])
    if dry_run:
        cmd.append("--dry-run")

    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, timeout=20, check=False)
    except Exception as exc:
        return tool_error(f"failed to emit wiki candidate: {exc}")
    if completed.returncode != 0:
        return tool_error((completed.stderr or completed.stdout or "candidate emitter failed").strip())
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"raw": completed.stdout.strip()}
    return tool_result(payload)


EMIT_WIKI_UPDATE_CANDIDATE_SCHEMA = {
    "name": "emit_wiki_update_candidate",
    "description": (
        "PD One/Hermes-only: emit a structured company-wiki update candidate "
        "from Mattermost conversation context. This does not edit canonical wiki "
        "pages; Hermes/PD Neo intake validates, reviews, and applies separately."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "entity_type": {"type": "string", "enum": sorted(ENTITY_TYPES)},
            "entity_id": {"type": "string", "description": "Stable opaque ID or short normalized name for the entity."},
            "entity_display_name": {"type": "string", "description": "Human-readable entity name."},
            "update_type": {"type": "string", "enum": sorted(UPDATE_TYPES)},
            "detail": {
                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}],
                "description": "One to five concise factual details; do not include raw transcript dumps or secrets.",
            },
            "source_channel_id": {"type": "string"},
            "source_post_id": {"type": "string"},
            "source_thread_id": {"type": "string"},
            "message_ref": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
            "domain": {"type": "string", "default": "general"},
            "risk": {"type": "string", "enum": sorted(RISKS), "default": "review_required"},
            "sensitivity": {"type": "string", "enum": sorted(SENSITIVITIES), "default": "internal"},
            "recommended_action": {"type": "string", "enum": sorted(ACTIONS), "default": "review"},
            "summary_zh_tw": {"type": "string"},
            "summary_en": {"type": "string"},
            "suggested_section": {"type": "string"},
            "excerpt": {"type": "string", "description": "Short excerpt only, never a full raw transcript."},
            "agent": {"type": "string", "default": "employee-assistant"},
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["entity_type", "entity_id", "entity_display_name", "update_type", "detail", "source_channel_id"],
    },
}


registry.register(
    name="emit_wiki_update_candidate",
    toolset="pd_one_wiki",
    schema=EMIT_WIKI_UPDATE_CANDIDATE_SCHEMA,
    handler=lambda args, **kw: emit_wiki_update_candidate(
        entity_type=args.get("entity_type", ""),
        entity_id=args.get("entity_id", ""),
        entity_display_name=args.get("entity_display_name", ""),
        update_type=args.get("update_type", ""),
        detail=args.get("detail"),
        source_channel_id=args.get("source_channel_id", ""),
        source_post_id=args.get("source_post_id", ""),
        source_thread_id=args.get("source_thread_id", ""),
        message_ref=args.get("message_ref"),
        domain=args.get("domain", "general"),
        risk=args.get("risk", "review_required"),
        sensitivity=args.get("sensitivity", "internal"),
        recommended_action=args.get("recommended_action", "review"),
        summary_zh_tw=args.get("summary_zh_tw", ""),
        summary_en=args.get("summary_en", ""),
        suggested_section=args.get("suggested_section", "Recent observations / 最近觀察"),
        excerpt=args.get("excerpt", ""),
        agent=args.get("agent", "employee-assistant"),
        dry_run=bool(args.get("dry_run", False)),
        task_id=kw.get("task_id"),
    ),
    check_fn=_check_reqs,
    emoji="🧾",
    max_result_size_chars=20_000,
)
