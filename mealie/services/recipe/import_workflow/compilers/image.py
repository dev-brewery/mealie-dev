import os

from mealie.schema.group.ai_providers import AIProviderOut
from mealie.schema.openai.compiled_source import OpenAICompiledSource
from mealie.services.openai import OpenAILocalImage

from .base import COMPILE_SOURCE_PROMPT, SourceCompiler, SourceType


class ImageCompiler(SourceCompiler):
    """Reads uploaded images. Runs on the group's image provider, since it needs vision."""

    source_type = SourceType.IMAGES
    progress_key = "recipe.create-progress.reading-images-with-ai"

    def can_compile(self) -> bool:
        # images can also be imported with OCR alone, in which case there's no image provider to ask
        return bool(self.ctx.input.images) and self.ctx.ai.image_provider is not None

    def _provider(self) -> AIProviderOut | None:
        """The provider to read the images with. None uses the group's image provider."""
        return None

    async def compile(self) -> OpenAICompiledSource | None:
        images = self.ctx.input.images
        attachments = [OpenAILocalImage(filename=os.path.basename(image), path=image) for image in images]

        noun = "images" if len(images) > 1 else "image"
        message = f"Attached {'are' if len(images) > 1 else 'is'} {len(images)} {noun} of a single recipe."

        return await self.ctx.ai.get_response(
            self.ctx.ai.get_prompt(COMPILE_SOURCE_PROMPT),
            message,
            response_schema=OpenAICompiledSource,
            attachments=attachments,
            provider=self._provider(),
        )


class FallbackImageCompiler(ImageCompiler):
    """
    Reads uploaded images with the group's fallback image provider. Only reached when the image
    provider failed to read them (raised or returned nothing); an image provider that read the images
    and found no recipe in them isn't a failure, so it isn't retried.
    """

    progress_key = "recipe.create-progress.reading-images-with-fallback-ai"

    def can_compile(self) -> bool:
        return super().can_compile() and self.ctx.ai.image_fallback_provider is not None

    def _provider(self) -> AIProviderOut | None:
        return self.ctx.ai.image_fallback_provider
