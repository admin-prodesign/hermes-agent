"""Rewrite absolute release paths in profile config with ruamel's round-trip loader."""

from __future__ import annotations

from io import StringIO
from pathlib import Path


def swap_prefix(value: str, old: str, new: str) -> str:
    old_s = old.rstrip("/")
    new_s = new.rstrip("/")
    if value == old_s:
        return new_s
    prefix = old_s + "/"
    if value.startswith(prefix):
        return new_s + value[len(old_s):]
    return value


def rewrite_tree(node, old: str, new: str) -> int:
    """In-place replacement. Returns how many strings changed."""
    count = 0
    if isinstance(node, dict):
        for key in list(node.keys()):
            value = node[key]
            if isinstance(value, str):
                replaced = swap_prefix(value, old, new)
                if replaced != value:
                    node[key] = replaced
                    count += 1
            else:
                count += rewrite_tree(value, old, new)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            if isinstance(value, str):
                replaced = swap_prefix(value, old, new)
                if replaced != value:
                    node[index] = replaced
                    count += 1
            else:
                count += rewrite_tree(value, old, new)
    return count


def rewrite_yaml_text(text: str, old: str, new: str) -> tuple[str, int]:
    from ruamel.yaml import YAML

    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    data = yaml.load(text)
    if data is None:
        return text, 0
    count = rewrite_tree(data, old, new)
    if count == 0:
        return text, 0
    buffer = StringIO()
    yaml.dump(data, buffer)
    return buffer.getvalue(), count


def rewrite_file(path: Path, old: str, new: str, backup: Path | None = None) -> int:
    original = path.read_text(encoding="utf-8-sig")
    updated, count = rewrite_yaml_text(original, old, new)
    if count == 0:
        return 0
    if backup is not None:
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(original, encoding="utf-8")
    tmp = path.with_name(path.name + ".nemo-tmp")
    tmp.write_text(updated, encoding="utf-8")
    tmp.replace(path)
    return count
