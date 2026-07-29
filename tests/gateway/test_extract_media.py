"""Tests for explicit MEDIA: attachment extraction."""

from unittest.mock import patch

from gateway.platforms.base import BasePlatformAdapter


def test_extract_media_deduplicates_repeated_bilingual_attachment_path():
    """One shared attachment mentioned in both language sections uploads once."""
    content = (
        "**English**\n"
        "Artifact package:\n"
        "MEDIA:/home/prodesign/artifacts/incident-dashboard.zip\n\n"
        "**繁體中文**\n"
        "產物壓縮包：\n"
        "MEDIA:/home/prodesign/artifacts/incident-dashboard.zip\n"
    )

    media, cleaned = BasePlatformAdapter.extract_media(content)

    assert media == [("/home/prodesign/artifacts/incident-dashboard.zip", False)]
    assert "MEDIA:" not in cleaned
    assert "**English**" in cleaned
    assert "**繁體中文**" in cleaned


def test_extract_media_deduplicates_tilde_and_expanded_same_local_path():
    with patch("os.path.expanduser", side_effect=lambda p: p.replace("~/", "/home/prodesign/", 1)):
        media, cleaned = BasePlatformAdapter.extract_media(
            "MEDIA:~/artifacts/report.pdf\nMEDIA:/home/prodesign/artifacts/report.pdf"
        )

    assert media == [("/home/prodesign/artifacts/report.pdf", False)]
    assert "MEDIA:" not in cleaned


def test_extract_media_keeps_distinct_paths_in_order():
    media, cleaned = BasePlatformAdapter.extract_media(
        "MEDIA:/tmp/a.zip\nMEDIA:/tmp/b.zip\nMEDIA:/tmp/a.zip"
    )

    assert media == [("/tmp/a.zip", False), ("/tmp/b.zip", False)]
    assert "MEDIA:" not in cleaned
