"""Store immutable Generoso contract versions.

Revision ID: 041_generoso_versions
Revises: 040_cristal_blue_ma
"""
from pathlib import Path
from hashlib import sha256
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "041_generoso_versions"
down_revision = "040_cristal_blue_ma"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generoso_tariff_versions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("content_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("effective_on", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("contract", JSONB(), nullable=False),
    )
    op.create_index("ix_generoso_tariff_versions_effective_on", "generoso_tariff_versions", ["effective_on"])
    op.create_table(
        "generoso_operations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("reference", sa.String(120), nullable=False, unique=True),
        sa.Column("occurred_on", sa.DateTime(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("recorded_by_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.create_index("ix_generoso_operations_occurred_on", "generoso_operations", ["occurred_on"])
    snapshot = Path(__file__).resolve().parents[2] / "data" / "tariffs" / "generoso" / "contract-2026.json"
    document = snapshot.read_text(encoding="utf-8")
    op.get_bind().execute(sa.text("""
        INSERT INTO generoso_tariff_versions (id, content_sha256, effective_on, created_at, contract)
        VALUES (:id, :digest, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CAST(:contract AS jsonb))
        ON CONFLICT (content_sha256) DO NOTHING
    """), {"id": str(uuid.uuid4()), "digest": sha256(document.encode("utf-8")).hexdigest(), "contract": document})


def downgrade() -> None:
    op.drop_index("ix_generoso_operations_occurred_on", table_name="generoso_operations")
    op.drop_table("generoso_operations")
    op.drop_index("ix_generoso_tariff_versions_effective_on", table_name="generoso_tariff_versions")
    op.drop_table("generoso_tariff_versions")
