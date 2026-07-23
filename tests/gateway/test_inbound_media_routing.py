"""Regression tests for gateway inbound media classification."""

from types import SimpleNamespace

from gateway.platforms.base import MessageType
from gateway.run import _event_media_is_image, _is_inbound_image_media


def test_photo_event_does_not_treat_document_mime_as_image():
    assert not _is_inbound_image_media(
        "/tmp/cache/19LH-3-桶-含縮水成品圖.stp",
        "application/octet-stream",
        MessageType.PHOTO,
    )


def test_photo_event_accepts_real_image_mime():
    assert _is_inbound_image_media(
        "/tmp/cache/image.png",
        "image/png",
        MessageType.PHOTO,
    )


def test_legacy_photo_event_without_mime_uses_file_extension():
    assert _is_inbound_image_media(
        "/tmp/cache/screenshot.jpg",
        "",
        MessageType.PHOTO,
    )
    assert not _is_inbound_image_media(
        "/tmp/cache/model.stp",
        "",
        MessageType.PHOTO,
    )


def test_mixed_photo_event_does_not_classify_mime_less_word_document_as_image():
    event = SimpleNamespace(
        message_type=MessageType.PHOTO,
        media_urls=[
            "/tmp/cache/screenshot.png",
            "/tmp/cache/mold-repair-procedure.doc",
        ],
        media_types=["image/png", ""],
    )

    assert _event_media_is_image(event, 0)
    assert not _event_media_is_image(event, 1)


def test_mime_less_photo_without_extension_falls_back_to_message_type():
    event = SimpleNamespace(
        message_type=MessageType.PHOTO,
        media_urls=["https://files.example.invalid/opaque-id"],
        media_types=[""],
    )

    assert _event_media_is_image(event, 0)


def test_mime_less_photo_url_ignores_query_when_checking_extension():
    event = SimpleNamespace(
        message_type=MessageType.PHOTO,
        media_urls=["https://files.example.invalid/screenshot.png?download=1"],
        media_types=[""],
    )

    assert _event_media_is_image(event, 0)
