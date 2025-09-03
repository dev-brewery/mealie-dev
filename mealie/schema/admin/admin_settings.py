"""Schema for admin settings API with hybrid approach: Database preferences + Environment secrets."""

from pydantic import BaseModel, Field, computed_field


class AdminSettingsBase(BaseModel):
    """Base schema for admin settings."""
    
    # Image Scanning Provider Settings (User Preferences stored in DB)
    image_scanning_primary_provider: str | None = Field(
        default="none", description="Primary AI provider for image scanning"
    )
    image_scanning_secondary_provider: str | None = Field(
        default="none", description="Secondary AI provider for fallback"
    )
    image_scanning_enable_ocr_fallback: bool = Field(default=True, description="Enable OCR as final fallback method")
    
    # Model Selections (User Preferences stored in DB)
    openai_model: str | None = Field(default="gpt-4o-mini", description="OpenAI model to use")
    anthropic_model: str | None = Field(default="claude-3-5-sonnet-20241022", description="Anthropic model to use")
    gemini_model: str | None = Field(default="gemini-1.5-flash", description="Gemini model to use")
    ollama_model: str | None = Field(default="llava", description="Ollama model to use")
    ollama_base_url: str | None = Field(default="http://localhost:11434", description="Ollama base URL")


class AdminSettingsIn(AdminSettingsBase):
    """Schema for updating admin settings. API keys are validated against environment but not stored."""
    
    # NOTE: API keys are NOT stored in database, they must be set via environment variables
    # These fields are accepted for backward compatibility but ignored during processing
    openai_api_key: str | None = Field(default=None, description="OpenAI API Key (ignored - use environment)")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API Key (ignored - use environment)")
    gemini_api_key: str | None = Field(default=None, description="Google Gemini API Key (ignored - use environment)")


class AdminSettingsOut(AdminSettingsBase):
    """Schema for returning admin settings with computed environment-based API key status."""
    
    id: int = Field(description="Settings record ID")
    
    # API Key Status (computed from environment variables - no regular fields)
    @computed_field
    @property
    def openai_api_key_set(self) -> bool:
        """Check if OpenAI API key is available in environment."""
        from mealie.core.config import get_app_settings
        settings = get_app_settings()
        return bool(getattr(settings, 'OPENAI_API_KEY', None))
    
    @computed_field
    @property
    def anthropic_api_key_set(self) -> bool:
        """Check if Anthropic API key is available in environment."""
        from mealie.core.config import get_app_settings
        settings = get_app_settings()
        return bool(getattr(settings, 'ANTHROPIC_API_KEY', None))
    
    @computed_field  
    @property
    def gemini_api_key_set(self) -> bool:
        """Check if Gemini API key is available in environment."""
        from mealie.core.config import get_app_settings
        settings = get_app_settings()
        return bool(getattr(settings, 'GEMINI_API_KEY', None))
    
    @classmethod
    def from_db_model(cls, db_model) -> "AdminSettingsOut":
        """Convert database model to output schema with computed environment properties."""
        return cls(
            id=db_model.id,
            image_scanning_primary_provider=db_model.image_scanning_primary_provider,
            image_scanning_secondary_provider=db_model.image_scanning_secondary_provider,
            image_scanning_enable_ocr_fallback=db_model.image_scanning_enable_ocr_fallback,
            openai_model=db_model.openai_model,
            anthropic_model=db_model.anthropic_model,
            gemini_model=db_model.gemini_model,
            ollama_model=db_model.ollama_model,
            ollama_base_url=db_model.ollama_base_url,
        )

    class Config:
        from_attributes = True