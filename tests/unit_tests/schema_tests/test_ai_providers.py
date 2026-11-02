from uuid import uuid4

import pytest
from pydantic import ValidationError

from mealie.pkgs import ocr
from mealie.schema.group.ai_providers import (
    AIProviderCreate,
    AIProviderSettingsOut,
    AIProviderSummary,
)


class AIProviderCreateTests:
    def test_valid_create(self):
        provider = AIProviderCreate(name="test", api_key="key", model="gpt-4o")
        assert provider.name == "test"
        assert provider.model == "gpt-4o"
        assert provider.timeout == 300
        assert provider.base_url is None

    @pytest.mark.parametrize("field", ["name", "api_key", "model"])
    def test_empty_field_raises(self, field: str):
        data: dict = {"name": "test", "api_key": "key", "model": "gpt-4o", field: ""}
        with pytest.raises(ValidationError):
            AIProviderCreate(**data)

    @pytest.mark.parametrize("timeout", [-1, -100])
    def test_negative_timeout_raises(self, timeout: int):
        with pytest.raises(ValidationError):
            AIProviderCreate(name="test", api_key="key", model="gpt-4o", timeout=timeout)

    def test_zero_timeout_is_valid(self):
        provider = AIProviderCreate(name="test", api_key="key", model="gpt-4o", timeout=0)
        assert provider.timeout == 0

    @pytest.mark.parametrize("base_url", ["", None])
    def test_base_url_empty_becomes_none(self, base_url: str | None):
        provider = AIProviderCreate(name="test", api_key="key", model="gpt-4o", base_url=base_url)
        assert provider.base_url is None

    def test_api_key_excluded_from_serialization(self):
        provider = AIProviderCreate(name="test", api_key="secret", model="gpt-4o")
        dumped = provider.model_dump()
        assert "api_key" not in dumped

    def test_api_key_excluded_from_json(self):
        provider = AIProviderCreate(name="test", api_key="secret", model="gpt-4o")
        json_str = provider.model_dump_json()
        assert "api_key" not in json_str
        assert "secret" not in json_str


class AIProviderSettingsOutTests:
    def _make_settings(
        self,
        *,
        default_provider_id=None,
        audio_provider_id=None,
        image_provider_id=None,
        image_fallback_provider_id=None,
        ocr_fallback_enabled=False,
        providers=None,
    ) -> AIProviderSettingsOut:
        if providers is None:
            providers = []
        return AIProviderSettingsOut(
            default_provider_id=default_provider_id,
            audio_provider_id=audio_provider_id,
            image_provider_id=image_provider_id,
            image_fallback_provider_id=image_fallback_provider_id,
            ocr_fallback_enabled=ocr_fallback_enabled,
            providers=providers,
        )

    # --- ai_enabled ---

    def test_ai_enabled_false_when_no_default(self):
        s = self._make_settings()
        assert not s.ai_enabled

    def test_ai_enabled_true_when_default_set(self):
        pid = uuid4()
        s = self._make_settings(default_provider_id=pid, providers=[AIProviderSummary(id=pid, name="p")])
        assert s.ai_enabled

    # --- audio_provider_enabled ---

    def test_audio_provider_disabled_when_no_default(self):
        audio_id = uuid4()
        s = self._make_settings(
            audio_provider_id=audio_id,
            providers=[AIProviderSummary(id=audio_id, name="audio")],
        )
        # audio_provider_id is valid, but validate_providers sets audio_provider_id to None
        # because without default_provider_id, it would be fine; let's test audio_provider_enabled
        # which requires ai_enabled to be True
        assert not s.ai_enabled
        assert not s.audio_provider_enabled

    def test_audio_provider_disabled_when_only_default_set(self):
        pid = uuid4()
        s = self._make_settings(default_provider_id=pid, providers=[AIProviderSummary(id=pid, name="p")])
        assert s.ai_enabled
        assert not s.audio_provider_enabled

    def test_audio_provider_enabled_when_both_set(self):
        pid = uuid4()
        audio_id = uuid4()
        s = self._make_settings(
            default_provider_id=pid,
            audio_provider_id=audio_id,
            providers=[AIProviderSummary(id=pid, name="p"), AIProviderSummary(id=audio_id, name="audio")],
        )
        assert s.ai_enabled
        assert s.audio_provider_enabled

    # --- image_provider_enabled ---

    def test_image_provider_disabled_when_no_default(self):
        image_id = uuid4()
        s = self._make_settings(
            image_provider_id=image_id,
            providers=[AIProviderSummary(id=image_id, name="img")],
        )
        assert not s.ai_enabled
        assert not s.image_provider_enabled

    def test_image_provider_disabled_when_only_default_set(self):
        pid = uuid4()
        s = self._make_settings(default_provider_id=pid, providers=[AIProviderSummary(id=pid, name="p")])
        assert s.ai_enabled
        assert not s.image_provider_enabled

    def test_image_provider_enabled_when_both_set(self):
        pid = uuid4()
        image_id = uuid4()
        s = self._make_settings(
            default_provider_id=pid,
            image_provider_id=image_id,
            providers=[AIProviderSummary(id=pid, name="p"), AIProviderSummary(id=image_id, name="img")],
        )
        assert s.ai_enabled
        assert s.image_provider_enabled

    # --- image_fallback_provider_enabled ---

    def _fallback_settings(self, *, with_image_provider: bool = True, same_as_image: bool = False):
        pid, image_id, fallback_id = uuid4(), uuid4(), uuid4()
        if same_as_image:
            fallback_id = image_id
        return self._make_settings(
            default_provider_id=pid,
            image_provider_id=image_id if with_image_provider else None,
            image_fallback_provider_id=fallback_id,
            providers=[
                AIProviderSummary(id=pid, name="p"),
                AIProviderSummary(id=image_id, name="img"),
                AIProviderSummary(id=fallback_id, name="fallback"),
            ],
        )

    def test_image_fallback_provider_enabled_with_image_provider(self):
        s = self._fallback_settings()
        assert s.image_provider_enabled
        assert s.image_fallback_provider_enabled

    def test_image_fallback_provider_disabled_without_image_provider(self):
        s = self._fallback_settings(with_image_provider=False)
        assert not s.image_provider_enabled
        assert not s.image_fallback_provider_enabled

    def test_image_fallback_provider_disabled_when_same_as_image_provider(self):
        s = self._fallback_settings(same_as_image=True)
        assert s.image_provider_enabled
        assert not s.image_fallback_provider_enabled

    def test_image_fallback_provider_disabled_when_unset(self):
        s = self._make_settings()
        assert s.image_fallback_provider_id is None
        assert not s.image_fallback_provider_enabled

    # --- OCR fallback ---

    @pytest.fixture()
    def tesseract(self, monkeypatch: pytest.MonkeyPatch):
        """Stands in for Tesseract being installed, or not; set `.installed` in the test"""
        state = type("Tesseract", (), {"installed": True})()
        monkeypatch.setattr(ocr, "is_available", lambda languages: state.installed)
        return state

    def _ocr_settings(self, *, with_default: bool = True, with_image_provider: bool = False, enabled: bool = True):
        pid, image_id = uuid4(), uuid4()
        return self._make_settings(
            default_provider_id=pid if with_default else None,
            image_provider_id=image_id if with_image_provider else None,
            ocr_fallback_enabled=enabled,
            providers=[AIProviderSummary(id=pid, name="p"), AIProviderSummary(id=image_id, name="img")],
        )

    def test_image_import_enabled_with_ocr_only(self, tesseract):
        s = self._ocr_settings()
        assert s.ocr_available
        assert s.ocr_fallback_active
        assert not s.image_provider_enabled
        assert s.image_import_enabled

    def test_image_import_enabled_with_image_provider_only(self, tesseract):
        tesseract.installed = False
        s = self._ocr_settings(with_image_provider=True, enabled=False)
        assert not s.ocr_fallback_active
        assert s.image_import_enabled

    def test_ocr_inactive_when_tesseract_is_missing(self, tesseract):
        tesseract.installed = False
        s = self._ocr_settings()
        assert not s.ocr_available
        assert not s.ocr_fallback_active
        assert not s.image_import_enabled

    def test_ocr_inactive_without_default_provider(self, tesseract):
        # OCR only reads the text; the default provider still has to build the recipe from it
        s = self._ocr_settings(with_default=False)
        assert not s.ai_enabled
        assert not s.ocr_fallback_active
        assert not s.image_import_enabled

    def test_ocr_inactive_when_not_enabled(self, tesseract):
        s = self._ocr_settings(enabled=False)
        assert s.ocr_available
        assert not s.ocr_fallback_active
        assert not s.image_import_enabled

    # --- validate_providers model validator ---

    def test_validate_providers_strips_unknown_image_fallback(self):
        pid = uuid4()
        image_id = uuid4()
        providers = [AIProviderSummary(id=pid, name="p"), AIProviderSummary(id=image_id, name="img")]
        s = self._make_settings(
            default_provider_id=pid,
            image_provider_id=image_id,
            image_fallback_provider_id=uuid4(),
            providers=providers,
        )
        assert s.image_provider_id == image_id
        assert s.image_fallback_provider_id is None
        assert not s.image_fallback_provider_enabled

    def test_validate_providers_strips_unknown_default(self):
        s = self._make_settings(default_provider_id=uuid4(), providers=[])
        assert s.default_provider_id is None
        assert not s.ai_enabled

    def test_validate_providers_strips_unknown_audio(self):
        pid = uuid4()
        providers = [AIProviderSummary(id=pid, name="p")]
        s = self._make_settings(default_provider_id=pid, audio_provider_id=uuid4(), providers=providers)
        assert s.default_provider_id == pid
        assert s.audio_provider_id is None

    def test_validate_providers_strips_unknown_image(self):
        pid = uuid4()
        providers = [AIProviderSummary(id=pid, name="p")]
        s = self._make_settings(default_provider_id=pid, image_provider_id=uuid4(), providers=providers)
        assert s.default_provider_id == pid
        assert s.image_provider_id is None

    def test_validate_providers_keeps_valid_ids(self):
        pid = uuid4()
        audio_id = uuid4()
        image_id = uuid4()
        providers = [
            AIProviderSummary(id=pid, name="p"),
            AIProviderSummary(id=audio_id, name="audio"),
            AIProviderSummary(id=image_id, name="img"),
        ]
        s = self._make_settings(
            default_provider_id=pid,
            audio_provider_id=audio_id,
            image_provider_id=image_id,
            providers=providers,
        )
        assert s.default_provider_id == pid
        assert s.audio_provider_id == audio_id
        assert s.image_provider_id == image_id

    def test_validate_providers_strips_all_if_empty_list(self):
        pid = uuid4()
        s = self._make_settings(
            default_provider_id=pid,
            audio_provider_id=uuid4(),
            image_provider_id=uuid4(),
            providers=[],
        )
        assert s.default_provider_id is None
        assert s.audio_provider_id is None
        assert s.image_provider_id is None

    def test_validate_providers_partial_strip(self):
        """Only the IDs pointing to missing providers are stripped."""
        pid = uuid4()
        audio_id = uuid4()
        providers = [AIProviderSummary(id=pid, name="p"), AIProviderSummary(id=audio_id, name="audio")]
        s = self._make_settings(
            default_provider_id=pid,
            audio_provider_id=audio_id,
            image_provider_id=uuid4(),  # not in list → stripped
            providers=providers,
        )
        assert s.default_provider_id == pid
        assert s.audio_provider_id == audio_id
        assert s.image_provider_id is None
