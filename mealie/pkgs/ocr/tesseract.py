import functools
from pathlib import Path

from PIL import Image, ImageOps

from mealie.core.root_logger import get_logger

# Importing the img package registers the HEIC opener with Pillow, so phone photos can be read too
from mealie.pkgs import img  # noqa: F401

logger = get_logger()

MAX_IMAGE_DIMENSION = 4000
"""Larger images are scaled down first; Tesseract gains nothing from more pixels, only time"""


class OCRUnavailableError(Exception):
    """Tesseract, or one of the requested language packs, isn't installed"""


def _split_languages(languages: str) -> list[str]:
    return [language.strip() for language in languages.split("+") if language.strip()]


@functools.cache
def is_available(languages: str = "eng") -> bool:
    """
    Whether OCR can run: pytesseract is installed, the Tesseract binary can be found, and every
    requested language pack is installed. Cached, since it shells out to Tesseract; installing
    Tesseract or a language pack takes effect after a restart.
    """

    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        installed = set(pytesseract.get_languages(config=""))
    except Exception as e:
        logger.info(f"OCR is unavailable, Tesseract could not be run ({e.__class__.__name__}: {e})")
        return False

    if missing := [language for language in _split_languages(languages) if language not in installed]:
        logger.warning(f"OCR is unavailable, Tesseract language packs are missing: {', '.join(missing)}")
        return False

    return True


def _prepare(image: Image.Image) -> Image.Image:
    # phone photos are usually stored sideways with an EXIF rotation; Tesseract reads them as-is
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
    return image


def image_to_text(path: Path, languages: str = "eng", timeout: int = 60) -> str:
    """
    Read the text in an image with Tesseract. Blocking: call it from a worker thread in async code.

    Raises OCRUnavailableError if Tesseract can't run, and RuntimeError if it times out.
    """

    if not is_available(languages):
        raise OCRUnavailableError(f"Tesseract is not available for languages '{languages}'")

    import pytesseract

    with Image.open(path) as image:
        prepared = _prepare(image)

    return pytesseract.image_to_string(prepared, lang="+".join(_split_languages(languages)), timeout=timeout).strip()
