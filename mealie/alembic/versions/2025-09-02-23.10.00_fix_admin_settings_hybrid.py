"""fix admin settings for hybrid approach

Revision ID: fix_admin_settings_hybrid
Revises: add_admin_settings
Create Date: 2025-09-02 23:10:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "fix_admin_settings_hybrid"
down_revision = "add_admin_settings"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the table if it exists (in case the previous migration partially completed)
    op.execute("DROP TABLE IF EXISTS admin_settings")
    
    # Create admin_settings table without API key fields (hybrid approach)
    op.create_table(
        "admin_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),  # Fixed column name
        sa.Column("image_scanning_primary_provider", sa.String(), nullable=True),
        sa.Column("image_scanning_secondary_provider", sa.String(), nullable=True),
        sa.Column("image_scanning_enable_ocr_fallback", sa.Boolean(), nullable=False),
        # Model selections (NOT API keys - those are environment only)
        sa.Column("openai_model", sa.String(), nullable=True),
        sa.Column("anthropic_model", sa.String(), nullable=True),
        sa.Column("gemini_model", sa.String(), nullable=True),
        sa.Column("ollama_model", sa.String(), nullable=True),
        sa.Column("ollama_base_url", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Insert default settings for fresh installs (hybrid approach)
    op.execute(
        """
        INSERT INTO admin_settings (
            image_scanning_primary_provider,
            image_scanning_secondary_provider,
            image_scanning_enable_ocr_fallback,
            openai_model,
            anthropic_model,
            gemini_model,
            ollama_model,
            ollama_base_url
        ) VALUES (
            'none',
            'none', 
            1,
            'gpt-4o-mini',
            'claude-3-5-sonnet-20241022',
            'gemini-1.5-flash',
            'llava',
            'http://localhost:11434'
        )
        """
    )


def downgrade():
    op.drop_table("admin_settings")