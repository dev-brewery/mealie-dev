"""Repository for managing admin settings with hybrid approach: Database preferences + Environment secrets."""

from sqlalchemy.orm.session import Session

from mealie.db.models.admin.admin_settings import AdminSettings
from mealie.schema.admin.admin_settings import AdminSettingsOut


class RepositoryAdminSettings:
    def __init__(self, session: Session):
        self.session = session

    def get_settings(self) -> AdminSettingsOut:
        """Get the admin settings instance with automatic migration for existing setups."""
        instance = AdminSettings.get_instance(self.session)
        return AdminSettingsOut.from_db_model(instance)

    def update_settings(self, settings_data: dict) -> AdminSettingsOut:
        """Update admin settings preferences. API keys must be configured via environment variables."""
        instance = self.session.query(AdminSettings).first()
        if not instance:
            # Create new instance with migration support
            instance = AdminSettings.get_instance(self.session)
        
        # Update user preferences (validation happens in update_from_dict)
        # API keys are ignored and must be set via environment variables
        instance.update_from_dict(settings_data)
        self.session.commit()
        self.session.refresh(instance)
        
        return AdminSettingsOut.from_db_model(instance)