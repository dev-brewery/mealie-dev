import json
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import mealie
from mealie.lang import get_locale_provider
from mealie.lang.providers import TRANSLATIONS
from mealie.pkgs import ocr
from mealie.pkgs.safehttp.fetch import FetchResult
from mealie.schema.openai.compiled_source import OpenAICompiledSource
from mealie.services.openai.content import (
    MAX_SOURCE_CONTENT_LENGTH,
    TRUNCATION_NOTICE,
    truncate_source_content,
    truncate_source_parts,
)
from mealie.services.recipe.import_workflow.compilers import (
    DEFAULT_SOURCE_COMPILERS,
    FallbackImageCompiler,
    ImageCompiler,
    OCRImageCompiler,
)
from mealie.services.recipe.import_workflow.compilers.base import SourceCompiler, SourceType
from mealie.services.recipe.import_workflow.compilers.ocr import OCR_PREAMBLE
from mealie.services.recipe.import_workflow.context import WorkflowInput
from mealie.services.recipe.import_workflow.recipe_conversion import (
    DEFAULT_RECIPE_NAME,
    DEFAULT_RECIPE_SLUG,
    resolve_name_and_slug,
)
from mealie.services.recipe.import_workflow.steps.compile_source import CompileSourceStep
from mealie.services.recipe.import_workflow.workflow import DEFAULT_WORKFLOW_STEPS

MEALIE_DIR = Path(mealie.__file__).parent
PROGRESS_KEY_PATTERN = re.compile(r"[\"'](recipe\.create-progress\.[a-zA-Z0-9-]+)[\"']")
IMPORT_ERROR_KEY_PATTERN = re.compile(r"[\"'](recipe\.import-errors\.[a-zA-Z0-9-]+)[\"']")

translator = get_locale_provider("en-US")


def is_translatable(key: str) -> bool:
    """The JSON provider falls back to returning the key itself when it can't resolve one."""

    return translator.t(key) != key


def declared_progress_keys() -> list[str]:
    """Progress keys declared by the workflow's steps and source compilers."""

    keys = [step.progress_key for step in DEFAULT_WORKFLOW_STEPS if step.progress_key]
    keys += [compiler.progress_key for compiler in DEFAULT_SOURCE_COMPILERS if compiler.progress_key]
    return keys


def keys_in_source(pattern: re.Pattern) -> list[str]:
    """Every matching translation key referenced as a literal anywhere in the backend."""

    keys: set[str] = set()
    for path in MEALIE_DIR.rglob("*.py"):
        keys.update(pattern.findall(path.read_text()))

    return sorted(keys)


def progress_keys_in_source() -> list[str]:
    return keys_in_source(PROGRESS_KEY_PATTERN)


def import_error_keys_in_source() -> list[str]:
    return keys_in_source(IMPORT_ERROR_KEY_PATTERN)


def test_workflow_declares_keys():
    # guards the tests below against silently passing on an empty list
    assert declared_progress_keys()
    assert progress_keys_in_source()
    assert import_error_keys_in_source()


@pytest.mark.parametrize("key", declared_progress_keys())
def test_declared_progress_keys_are_translatable(key: str):
    assert is_translatable(key), f"Progress key '{key}' is missing from the backend translations"


@pytest.mark.parametrize("key", progress_keys_in_source())
def test_progress_keys_used_in_source_are_translatable(key: str):
    assert is_translatable(key), f"Progress key '{key}' is missing from the backend translations"


@pytest.mark.parametrize("key", import_error_keys_in_source())
def test_import_error_keys_are_translatable(key: str):
    """These are surfaced to the user, so an unresolved key shows up as raw text in the UI."""

    assert is_translatable(key), f"Import error key '{key}' is missing from the backend translations"


def test_short_content_is_not_truncated():
    content = "a" * 100
    assert truncate_source_content(content) == content


def test_content_at_the_limit_is_not_truncated():
    content = "a" * MAX_SOURCE_CONTENT_LENGTH
    assert truncate_source_content(content) == content


def test_long_content_is_truncated_and_marked():
    content = "a" * (MAX_SOURCE_CONTENT_LENGTH + 1)
    truncated = truncate_source_content(content)

    assert truncated.endswith(TRUNCATION_NOTICE)
    assert len(truncated) == MAX_SOURCE_CONTENT_LENGTH + len(TRUNCATION_NOTICE)


def test_content_can_be_truncated_to_a_custom_length():
    assert truncate_source_content("abcdef", max_length=3) == "abc" + TRUNCATION_NOTICE


def test_parts_that_fit_the_budget_are_left_alone():
    parts = ["a" * 10, "b" * 10]
    assert truncate_source_parts(parts, max_length=100) == parts


def test_parts_share_the_budget_evenly_when_all_are_too_long():
    parts = ["a" * 100, "b" * 100]
    assert truncate_source_parts(parts, max_length=10) == ["a" * 5 + TRUNCATION_NOTICE, "b" * 5 + TRUNCATION_NOTICE]


def test_a_short_part_is_not_crowded_out_by_a_long_one():
    """A huge webpage must not swallow the budget and drop the content pasted alongside it."""

    page = "a" * 1000
    pasted = "b" * 10

    truncated_page, truncated_pasted = truncate_source_parts([page, pasted], max_length=100)

    assert truncated_pasted == pasted
    assert truncated_page == "a" * 90 + TRUNCATION_NOTICE


def test_no_parts_is_not_an_error():
    assert truncate_source_parts([]) == []


def test_no_orphaned_import_error_keys():
    """Import error translations that nothing references anymore should be removed."""

    messages = json.loads((TRANSLATIONS / "en-US.json").read_text())
    defined = set(messages["recipe"]["import-errors"])
    used = {key.rsplit(".", 1)[-1] for key in import_error_keys_in_source()}

    assert defined - used == set()


def test_no_orphaned_progress_keys():
    """Progress translations that nothing references anymore should be removed."""

    messages = json.loads((TRANSLATIONS / "en-US.json").read_text())
    defined = set(messages["recipe"]["create-progress"])
    used = {key.rsplit(".", 1)[-1] for key in progress_keys_in_source()}

    assert defined - used == set()


class StubContext:
    """Only the parts of WorkflowContext that CompileSourceStep touches.

    The real one needs live repositories and an AI service, neither of which these tests reach.
    """

    def __init__(self, url: str | None = None, page_content: str | None = None) -> None:
        self.input = WorkflowInput(url=url, page_content=page_content)
        self.resolved_url: str | None = None
        self.progress: list[str] = []

    async def report_progress(self, key: str) -> None:
        self.progress.append(key)


class FailingUrlCompiler(SourceCompiler):
    """Stands in for the transcription compiler meeting a page that turns out to have no video."""

    source_type = SourceType.URL

    def can_compile(self) -> bool:
        return True

    async def compile(self) -> OpenAICompiledSource | None:
        raise RuntimeError("ERROR: unable to download video")


class UnreachableUrlCompiler(SourceCompiler):
    source_type = SourceType.URL

    def can_compile(self) -> bool:
        return True

    async def compile(self) -> OpenAICompiledSource | None:
        return OpenAICompiledSource(contains_recipe=True, content="from the second url compiler")


class EchoContentCompiler(SourceCompiler):
    source_type = SourceType.CONTENT

    def can_compile(self) -> bool:
        return True

    async def compile(self) -> OpenAICompiledSource | None:
        return OpenAICompiledSource(contains_recipe=True, content=self.content or "")


@pytest.mark.asyncio
async def test_a_failing_compiler_hands_over_to_the_next():
    step = CompileSourceStep(compilers=[FailingUrlCompiler, UnreachableUrlCompiler])

    compiled = await step._compile(StubContext(url="https://example.test/x"), SourceType.URL)

    assert compiled is not None
    assert compiled.content == "from the second url compiler"


@pytest.mark.asyncio
async def test_a_failing_url_compiler_falls_back_to_reading_the_page(monkeypatch: pytest.MonkeyPatch):
    """`can_compile` judges the shape of a URL, not whether the page really holds what it expects.

    yt-dlp recognises every cooking.nytimes.com/recipes/<id> URL, but most of those pages carry no
    video, so the download raises. That used to abort the whole import even though the page itself
    was perfectly readable.
    """
    monkeypatch.setattr(
        "mealie.services.recipe.import_workflow.steps.compile_source.resilient_fetch",
        _fake_fetch,
    )

    step = CompileSourceStep(compilers=[FailingUrlCompiler, EchoContentCompiler])
    ctx = StubContext(url="https://cooking.nytimes.com/recipes/785347515-heirloom-tomato-and-cheddar-pie")

    compiled = await step._compile_page(ctx)

    assert compiled is not None
    assert compiled.content == "<html>the recipe page</html>"
    assert "recipe.create-progress.fetching-webpage" in ctx.progress


async def _fake_fetch(url: str) -> FetchResult:
    return FetchResult(b"<html>the recipe page</html>", 200, url, httpx.Headers(), "utf-8")


@pytest.mark.asyncio
async def test_a_compiler_returning_nothing_also_hands_over():
    """The no-transcript path already returned None rather than raising; both must fall through."""

    class EmptyUrlCompiler(SourceCompiler):
        source_type = SourceType.URL

        def can_compile(self) -> bool:
            return True

        async def compile(self) -> OpenAICompiledSource | None:
            return None

    step = CompileSourceStep(compilers=[EmptyUrlCompiler, UnreachableUrlCompiler])

    compiled = await step._compile(StubContext(url="https://example.test/x"), SourceType.URL)

    assert compiled is not None
    assert compiled.content == "from the second url compiler"


class StubImageAI:
    """The parts of OpenAIService the image compilers touch, recording which provider each read used."""

    def __init__(
        self,
        *,
        fallback_provider: object | None,
        image_provider_fails: bool,
        image_provider: object | None = "image",
        ocr_fallback_active: bool = False,
    ) -> None:
        self.image_provider = image_provider
        self.image_fallback_provider = fallback_provider
        self.image_provider_fails = image_provider_fails
        self.provider_settings = SimpleNamespace(ocr_fallback_active=ocr_fallback_active)
        self.providers: list[object | None] = []

    def get_prompt(self, name: str) -> str:
        return name

    async def get_response(self, prompt, message, *, response_schema, attachments=None, provider=None):
        self.providers.append(provider)
        if provider is None and self.image_provider_fails:
            raise RuntimeError("image provider unavailable")
        return OpenAICompiledSource(contains_recipe=True, content=f"read by {provider or 'image provider'}")


class StubImageContext(StubContext):
    def __init__(self, ai: StubImageAI, images: list[Path]) -> None:
        super().__init__()
        self.input = WorkflowInput(images=images)
        self.ai = ai


def test_image_compilers_try_the_image_providers_before_ocr():
    image_compilers = [c for c in DEFAULT_SOURCE_COMPILERS if c.source_type is SourceType.IMAGES]
    assert image_compilers == [ImageCompiler, FallbackImageCompiler, OCRImageCompiler]


@pytest.mark.asyncio
async def test_fallback_image_provider_reads_images_the_image_provider_could_not(tmp_path: Path):
    ai = StubImageAI(fallback_provider="fallback", image_provider_fails=True)
    ctx = StubImageContext(ai, [tmp_path / "recipe.jpg"])
    step = CompileSourceStep(compilers=[ImageCompiler, FallbackImageCompiler])

    compiled = await step._compile(ctx, SourceType.IMAGES)

    assert compiled is not None
    assert compiled.content == "read by fallback"
    assert ai.providers == [None, "fallback"]
    assert ctx.progress == [ImageCompiler.progress_key, FallbackImageCompiler.progress_key]


@pytest.mark.asyncio
async def test_fallback_image_compiler_is_skipped_without_a_fallback_provider(tmp_path: Path):
    ai = StubImageAI(fallback_provider=None, image_provider_fails=True)
    ctx = StubImageContext(ai, [tmp_path / "recipe.jpg"])
    step = CompileSourceStep(compilers=[ImageCompiler, FallbackImageCompiler])

    compiled = await step._compile(ctx, SourceType.IMAGES)

    assert compiled is None
    assert ai.providers == [None]


@pytest.mark.asyncio
async def test_fallback_image_compiler_is_not_used_when_the_image_provider_succeeds(tmp_path: Path):
    ai = StubImageAI(fallback_provider="fallback", image_provider_fails=False)
    ctx = StubImageContext(ai, [tmp_path / "recipe.jpg"])
    step = CompileSourceStep(compilers=[ImageCompiler, FallbackImageCompiler])

    compiled = await step._compile(ctx, SourceType.IMAGES)

    assert compiled is not None
    assert ai.providers == [None]


@pytest.fixture()
def fake_ocr(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Stands in for Tesseract, reading each image's name as its text. Returns the images read, in order."""
    read: list[Path] = []

    def image_to_text(path: Path, languages: str = "eng", timeout: int = 60) -> str:
        read.append(path)
        return "" if path.stem.startswith("blank") else f"text of {path.stem}"

    monkeypatch.setattr(ocr, "image_to_text", image_to_text)
    return read


@pytest.mark.asyncio
async def test_ocr_reads_every_image_when_the_image_providers_fail(tmp_path: Path, fake_ocr: list[Path]):
    images = [tmp_path / "page-1.jpg", tmp_path / "page-2.jpg"]
    ai = StubImageAI(fallback_provider=None, image_provider_fails=True, ocr_fallback_active=True)
    ctx = StubImageContext(ai, images)
    step = CompileSourceStep(compilers=[ImageCompiler, FallbackImageCompiler, OCRImageCompiler])

    compiled = await step._compile(ctx, SourceType.IMAGES)

    assert compiled is not None
    assert fake_ocr == images
    assert ai.providers == [None]
    assert compiled.content.startswith(OCR_PREAMBLE)
    assert compiled.content.index("text of page-1") < compiled.content.index("text of page-2")
    assert "## Photo 2" in compiled.content
    assert ctx.progress[-1] == OCRImageCompiler.progress_key


@pytest.mark.asyncio
async def test_ocr_is_used_without_any_image_provider(tmp_path: Path, fake_ocr: list[Path]):
    ai = StubImageAI(fallback_provider=None, image_provider_fails=False, image_provider=None, ocr_fallback_active=True)
    ctx = StubImageContext(ai, [tmp_path / "recipe.jpg"])
    step = CompileSourceStep(compilers=[ImageCompiler, FallbackImageCompiler, OCRImageCompiler])

    compiled = await step._compile(ctx, SourceType.IMAGES)

    assert compiled is not None
    # no AI provider was asked to read the images
    assert ai.providers == []
    assert compiled.content == f"{OCR_PREAMBLE}\n\ntext of recipe"
    assert ctx.progress == [OCRImageCompiler.progress_key]


@pytest.mark.asyncio
async def test_ocr_is_not_used_when_an_image_provider_succeeds(tmp_path: Path, fake_ocr: list[Path]):
    ai = StubImageAI(fallback_provider=None, image_provider_fails=False, ocr_fallback_active=True)
    ctx = StubImageContext(ai, [tmp_path / "recipe.jpg"])
    step = CompileSourceStep(compilers=[ImageCompiler, FallbackImageCompiler, OCRImageCompiler])

    compiled = await step._compile(ctx, SourceType.IMAGES)

    assert compiled is not None
    assert fake_ocr == []


@pytest.mark.asyncio
async def test_ocr_is_skipped_when_not_active(tmp_path: Path, fake_ocr: list[Path]):
    ai = StubImageAI(fallback_provider=None, image_provider_fails=True, ocr_fallback_active=False)
    ctx = StubImageContext(ai, [tmp_path / "recipe.jpg"])
    step = CompileSourceStep(compilers=[ImageCompiler, FallbackImageCompiler, OCRImageCompiler])

    assert await step._compile(ctx, SourceType.IMAGES) is None
    assert fake_ocr == []


@pytest.mark.asyncio
async def test_ocr_that_finds_no_text_hands_over(tmp_path: Path, fake_ocr: list[Path]):
    ai = StubImageAI(fallback_provider=None, image_provider_fails=True, ocr_fallback_active=True)
    ctx = StubImageContext(ai, [tmp_path / "blank-1.jpg", tmp_path / "blank-2.jpg"])
    step = CompileSourceStep(compilers=[ImageCompiler, FallbackImageCompiler, OCRImageCompiler])

    assert await step._compile(ctx, SourceType.IMAGES) is None
    assert len(fake_ocr) == 2


class StubTranslator:
    """Translator is a Protocol with a single method, so a stub is enough here."""

    def __init__(self, translation: str | None = None) -> None:
        self.translation = translation

    def t(self, key, default=None, **kwargs) -> str:
        return self.translation if self.translation is not None else (default or key)


class NameContext:
    """Only the part of WorkflowContext that `resolve_name_and_slug` touches."""

    def __init__(self, translator=None) -> None:
        self.translator = translator or get_locale_provider("en-US")


def test_a_usable_name_is_kept():
    assert resolve_name_and_slug(NameContext(), "Grilled Cheese") == ("Grilled Cheese", "grilled-cheese")


@pytest.mark.parametrize("name", ["", "   ", "!!!", "🍞🧀"])
def test_an_unsluggable_name_falls_back_to_the_default(name: str):
    """A provider returning a junk name shouldn't throw away an otherwise good recipe."""

    assert resolve_name_and_slug(NameContext(), name) == (DEFAULT_RECIPE_NAME, DEFAULT_RECIPE_SLUG)


def test_the_default_name_is_translated():
    name, slug = resolve_name_and_slug(NameContext(StubTranslator("Neues Rezept")), "")

    assert (name, slug) == ("Neues Rezept", "neues-rezept")


def test_an_unsluggable_translation_falls_back_to_an_ascii_slug():
    """slugify can come back empty for a script it can't transliterate."""

    name, slug = resolve_name_and_slug(NameContext(StubTranslator("🍲")), "")

    assert (name, slug) == ("🍲", DEFAULT_RECIPE_SLUG)
