"""add image fallback provider to ai provider settings

Revision ID: 45fcbe0fb5ed
Revises: 071e03b4f851
Create Date: 2026-11-02 15:13:08.453376

"""

import sqlalchemy as sa
from alembic import op

import mealie.db.migration_types

# revision identifiers, used by Alembic.
revision = "45fcbe0fb5ed"
down_revision: str | None = "071e03b4f851"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

FK_NAME = "fk_ai_provider_settings_image_fallback_provider_id"


def upgrade():
    with op.batch_alter_table("ai_provider_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("image_fallback_provider_id", mealie.db.migration_types.GUID(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_ai_provider_settings_image_fallback_provider_id"),
            ["image_fallback_provider_id"],
            unique=False,
        )
        # named, so the downgrade can drop it on every database
        batch_op.create_foreign_key(FK_NAME, "ai_providers", ["image_fallback_provider_id"], ["id"])


def downgrade():
    with op.batch_alter_table("ai_provider_settings", schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_ai_provider_settings_image_fallback_provider_id"))
        batch_op.drop_column("image_fallback_provider_id")
