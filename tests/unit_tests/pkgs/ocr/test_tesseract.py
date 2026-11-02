"""
Tesseract is stood in for throughout, so these tests behave the same whether or not it's installed.
"""

from pathlib import Path

import pytesseract
import pytest
from PIL import Image

from mealie.pkgs import ocr
from mealie.pkgs.ocr import tesseract


@pytest.fixture(autouse=True)
def clear_availability_cache():
    tesseract.is_available.cache_clear()
    yield
    tesseract.is_available.cache_clear()


@pytest.fixture()
def installed_languages(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    languages = ["eng", "osd"]
    monkeypatch.setattr(pytesseract, "get_tesseract_version", lambda: "5.3.4")
    monkeypatch.setattr(pytesseract, "get_languages", lambda config="": languages)
    return languages


def test_is_available_when_tesseract_and_languages_are_installed(installed_languages: list[str]):
    assert ocr.is_available("eng")


def test_is_available_false_when_tesseract_is_missing(monkeypatch: pytest.MonkeyPatch):
    def missing():
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "get_tesseract_version", missing)

    assert not ocr.is_available("eng")


def test_is_available_false_when_a_language_pack_is_missing(installed_languages: list[str]):
    assert not ocr.is_available("eng+deu")


def test_is_available_ignores_blank_language_segments(installed_languages: list[str]):
    assert ocr.is_available(" eng + ")


def test_image_to_text_raises_when_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(tesseract, "is_available", lambda languages: False)

    with pytest.raises(ocr.OCRUnavailableError):
        ocr.image_to_text(tmp_path / "missing.jpg", "eng")


def test_image_to_text_prepares_the_image(
    installed_languages: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # a wide photo stored with EXIF "rotate 90" (orientation 6), the way phones save portrait shots
    path = tmp_path / "photo.jpg"
    photo = Image.new("RGB", (8000, 2000), "white")
    exif = photo.getexif()
    exif[0x0112] = 6
    photo.save(path, exif=exif)

    calls: list[dict] = []

    def image_to_string(image: Image.Image, lang: str, timeout: int) -> str:
        calls.append({"mode": image.mode, "size": image.size, "lang": lang, "timeout": timeout})
        return "  2 cups flour\n"

    monkeypatch.setattr(pytesseract, "image_to_string", image_to_string)

    text = ocr.image_to_text(path, "eng", timeout=30)

    assert text == "2 cups flour"
    assert len(calls) == 1
    call = calls[0]
    assert call["mode"] == "L"
    assert call["lang"] == "eng"
    assert call["timeout"] == 30
    # rotated upright (portrait), then scaled down to fit the maximum dimension
    width, height = call["size"]
    assert height > width
    assert max(width, height) == tesseract.MAX_IMAGE_DIMENSION
