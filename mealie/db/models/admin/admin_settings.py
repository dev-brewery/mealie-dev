"""Database model for admin settings that need to be configurable via UI."""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.models._model_utils.auto_init import auto_init


class AdminSettings(SqlAlchemyBase):
    __tablename__ = "admin_settings"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Image Scanning Provider Settings (User Preferences)
    image_scanning_primary_provider: Mapped[str | None] = mapped_column(String, default="none")
    image_scanning_secondary_provider: Mapped[str | None] = mapped_column(String, default="none")  
    image_scanning_enable_ocr_fallback: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Model Selections (User Preferences - NOT secrets)
    openai_model: Mapped[str | None] = mapped_column(String, default="gpt-4o-mini")
    anthropic_model: Mapped[str | None] = mapped_column(String, default="claude-3-5-sonnet-20241022")
    gemini_model: Mapped[str | None] = mapped_column(String, default="gemini-1.5-flash")
    ollama_model: Mapped[str | None] = mapped_column(String, default="llava")
    ollama_base_url: Mapped[str | None] = mapped_column(String, default="http://localhost:11434")
    
    # NOTE: API Keys are stored in environment variables, not in database

    @auto_init()
    def __init__(self, **kwargs) -> None:
        pass

    # Singleton pattern - there should only ever be one row
    @classmethod
    def get_instance(cls, session):
        """Get or create the single admin settings instance with smart migration."""
        from mealie.core.config import get_app_settings
        
        instance = session.query(cls).first()
        if not instance:
            # Create new instance with auto-migration for existing users
            instance = cls()
            session.add(instance)
            
            # Auto-migrate existing environment-only setups
            instance._auto_migrate_existing_config()
            
            session.commit()
            session.refresh(instance)
        else:
            # For existing instances, check if migration is needed
            # Only run migration if provider is still "none" (not yet configured)
            if instance.image_scanning_primary_provider == "none":
                instance._auto_migrate_existing_config()
                if instance.image_scanning_primary_provider != "none":
                    # Migration changed something, save it
                    session.commit()
                    session.refresh(instance)
        
        return instance
    
    def _auto_migrate_existing_config(self):
        """Auto-migrate existing environment-only configurations for users who previously used AI scanning.
        
        IMPORTANT: Only auto-migrate for users who actually used AI scanning before.
        Don't auto-migrate just because environment variables are present.
        Fresh installs should always start with 'none' requiring explicit user configuration.
        """
        from mealie.core.config import get_app_settings
        
        # Only auto-migrate if no provider is currently set
        if self.image_scanning_primary_provider != "none":
            return
            
        settings = get_app_settings()
        
        # Check for evidence of prior AI scanning usage
        has_prior_usage = self._detect_prior_ai_usage()
        
        if has_prior_usage:
            # Migration priority order for users with confirmed prior usage
            migration_priority = ["openai", "gemini", "anthropic", "ollama"]
            
            for provider in migration_priority:
                api_key_attr = f"{provider.upper()}_API_KEY"
                if hasattr(settings, api_key_attr) and getattr(settings, api_key_attr):
                    self.image_scanning_primary_provider = provider
                    break  # Take first available provider
    
    def _detect_prior_ai_usage(self) -> bool:
        """Detect if this user/system previously used AI scanning features.
        
        Uses API key validation as the primary indicator - if they have a valid,
        working OpenAI API key, they almost certainly intended to use AI scanning.
        """
        try:
            # Check for valid OpenAI API key - this is the most reliable indicator
            if self._validate_openai_api_key():
                return True
                
            # Could add other provider validation here in the future
            # (Anthropic, Gemini, etc.)
            
            return False
            
        except Exception:
            # If any error occurs during detection, err on the safe side
            return False
    
    def _validate_openai_api_key(self) -> bool:
        """Validate that the OpenAI API key is valid and working.
        
        Makes a simple API call to OpenAI to verify the key works.
        This is the most reliable way to detect intended AI usage.
        """
        try:
            from mealie.core.config import get_app_settings
            settings = get_app_settings()
            
            # Get the API key from environment
            api_key = getattr(settings, 'OPENAI_API_KEY', None)
            if not api_key or not api_key.strip():
                return False
            
            # Testing mode removed for production
                
            # Make a simple API call to validate the key
            import httpx
            
            # Use OpenAI's models endpoint for validation - it's lightweight
            response = httpx.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            
            # If we get a 200 response, the key is valid
            return response.status_code == 200
            
        except Exception:
            # If any error occurs (network, timeout, import, etc.), assume invalid
            return False
    
    @classmethod 
    def validate_provider_config(cls, provider: str) -> bool:
        """Validate that a provider has corresponding environment configuration."""
        if provider == "none":
            return True
            
        from mealie.core.config import get_app_settings
        settings = get_app_settings()
        
        api_key_attr = f"{provider.upper()}_API_KEY"
        return hasattr(settings, api_key_attr) and bool(getattr(settings, api_key_attr, None))

    def update_from_dict(self, data: dict) -> None:
        """Update settings from a dictionary, ignoring unknown keys and API keys."""
        valid_fields = {
            'image_scanning_primary_provider',
            'image_scanning_secondary_provider', 
            'image_scanning_enable_ocr_fallback',
            'ollama_base_url',
            'openai_model',
            'anthropic_model',
            'gemini_model',
            'ollama_model'
        }
        
        # Validate provider selections have corresponding environment keys
        for provider_field in ['image_scanning_primary_provider', 'image_scanning_secondary_provider']:
            if provider_field in data:
                provider = data[provider_field]
                if provider != "none" and not self.validate_provider_config(provider):
                    raise ValueError(f"Provider '{provider}' selected but no corresponding API key found in environment")
        
        for key, value in data.items():
            if key in valid_fields and hasattr(self, key):
                # Only update if value is not None or empty string (unless it's a boolean)
                if value is not None and (value != "" or isinstance(value, bool)):
                    setattr(self, key, value)
                    
            # Ignore API key fields - they should be in environment variables
            elif key.endswith('_api_key'):
                continue  # Skip API keys, they're handled by environment