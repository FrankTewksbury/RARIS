"""Add programs table for discovery v2.

Revision ID: 002_add_programs
Revises: 001_initial
Create Date: 2026-02-28
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "002_add_programs"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "programs",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column(
            "manifest_id",
            sa.String(100),
            sa.ForeignKey("manifests.id"),
            nullable=False,
        ),
        sa.Column("canonical_id", sa.String(255), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("administering_entity", sa.String(255), nullable=False),
        sa.Column("geo_scope", sa.String(20), nullable=False),
        sa.Column("jurisdiction", sa.String(120), nullable=True),
        sa.Column("benefits", sa.Text, nullable=True),
        sa.Column("eligibility", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="verification_pending"),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_snippet", sa.Text, nullable=True),
        sa.Column("source_urls", postgresql.JSONB, nullable=True),
        sa.Column("provenance_links", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("needs_human_review", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_programs_manifest_id", "programs", ["manifest_id"])


def downgrade() -> None:
    op.drop_index("ix_programs_manifest_id", table_name="programs")
    op.drop_table("programs")
