"""Regression tests for gateway inbound media classification."""

from gateway.platforms.base import MessageType
from gateway.run import _is_inbound_image_media


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
