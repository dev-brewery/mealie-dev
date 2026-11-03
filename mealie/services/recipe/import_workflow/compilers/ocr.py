import asyncio
from pathlib import Path

from mealie.core.config import get_app_settings
from mealie.pkgs import ocr
from mealie.schema.openai.compiled_source import OpenAICompiledSource

from .base import SourceCompiler, SourceType

OCR_PREAMBLE = (
    "The text below was read from photos of a recipe with OCR (optical character recognition), not by "
    "a person or an AI model, so it may contain misread characters, broken lines, or text from outside "
    "the recipe. Each photo is a page of the same recipe."
)


class OCRImageCompiler(SourceCompiler):
    """
    Reads uploaded images with Tesseract OCR, as a last resort after the AI image providers: when the
    group has no image provider, or every image provider failed to read the images. No AI provider
    sees the images; the text read from them is handed to the default provider to build the recipe.
    """

    source_type = SourceType.IMAGES
    progress_key = "recipe.create-progress.reading-images-with-ocr"

    def can_compile(self) -> bool:
        settings = self.ctx.ai.provider_settings
        return bool(self.ctx.input.images) and bool(settings and settings.ocr_fallback_active)

    def _read_images(self, images: list[Path], languages: str) -> list[str]:
        # one image at a time, so a large upload doesn't start a Tesseract process per photo at once
        return [ocr.image_to_text(image, languages) for image in images]

    async def compile(self) -> OpenAICompiledSource | None:
        languages = get_app_settings().OCR_LANGUAGES
        texts = await asyncio.to_thread(self._read_images, self.ctx.input.images, languages)

        pages = [(number, text) for number, text in enumerate(texts, start=1) if text.strip()]
        if not pages:
            self.logger.info("OCR found no text in the uploaded images")
            return None

        if len(texts) > 1:
            content = "\n\n".join(f"## Photo {number}\n\n{text}" for number, text in pages)
        else:
            content = pages[0][1]

        return OpenAICompiledSource(
            contains_recipe=True,
            content=f"{OCR_PREAMBLE}\n\n{content}",
            language=None,
            image_url=None,
        )
