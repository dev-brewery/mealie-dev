"""
The ocr package reads text from images with Tesseract. Like the img package, it isn't coupled to the
rest of Mealie: callers pass in the languages to read rather than it reading Mealie's settings.
"""

from .tesseract import OCRUnavailableError, image_to_text, is_available

__all__ = ["OCRUnavailableError", "image_to_text", "is_available"]
