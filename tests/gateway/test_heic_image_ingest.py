"""HEIC/HEIF inbound image handling."""

import io
from pathlib import Path

from PIL import Image
import pillow_heif

from gateway.platforms.base import (
    _looks_like_heif,
    cache_image_from_bytes,
    SUPPORTED_IMAGE_DOCUMENT_TYPES,
)
from gateway.run import _is_inbound_image_media
from gateway.platforms.base import MessageType


def _tiny_heic_bytes() -> bytes:
    pillow_heif.register_heif_opener()
    image = Image.new("RGB", (8, 8), (220, 20, 30))
    out = io.BytesIO()
    image.save(out, format="HEIF")
    return out.getvalue()


def test_cache_image_from_bytes_converts_heic_to_jpeg(tmp_path, monkeypatch):
    monkeypatch.setattr("gateway.platforms.base.IMAGE_CACHE_DIR", tmp_path)
    raw = _tiny_heic_bytes()

    assert _looks_like_heif(raw)
    cached = Path(cache_image_from_bytes(raw, ext=".heic"))

    assert cached.suffix == ".jpg"
    assert cached.exists()
    assert cached.read_bytes()[:3] == b"\xff\xd8\xff"
    with Image.open(cached) as decoded:
        assert decoded.size == (8, 8)
        assert decoded.format == "JPEG"


def test_heic_document_types_are_supported_as_images():
    assert SUPPORTED_IMAGE_DOCUMENT_TYPES[".heic"] == "image/heic"
    assert SUPPORTED_IMAGE_DOCUMENT_TYPES[".heif"] == "image/heif"
    assert _is_inbound_image_media("/tmp/photo.heic", "", MessageType.PHOTO)
    assert _is_inbound_image_media("/tmp/photo.heif", "", MessageType.PHOTO)
    assert _is_inbound_image_media("/tmp/photo.bin", "image/heic", MessageType.DOCUMENT)
