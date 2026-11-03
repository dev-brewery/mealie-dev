"""add ocr fallback to ai provider settings

Revision ID: 0ec641a986a2
Revises: 45fcbe0fb5ed
Create Date: 2026-11-02 15:22:47.745435

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0ec641a986a2"
down_revision: str | None = "45fcbe0fb5ed"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade():
    with op.batch_alter_table("ai_provider_settings", schema=None) as batch_op:
        # existing groups start with the OCR fallback off
        batch_op.add_column(
            sa.Column(
                "ocr_fallback_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.sql.expression.false(),
            )
        )


def downgrade():
    with op.batch_alter_table("ai_provider_settings", schema=None) as batch_op:
        batch_op.drop_column("ocr_fallback_enabled")
