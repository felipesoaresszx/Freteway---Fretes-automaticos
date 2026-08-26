"""SSW integration validation metadata.

Revision ID: 018_ssw_integration_validation
Revises: 017_carrier_profile_fields
"""
from alembic import op
import sqlalchemy as sa

revision = "018_ssw_integration_validation"
down_revision = "017_carrier_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("carrier_integrations", sa.Column("validation_message", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("carrier_integrations", "validation_message")
