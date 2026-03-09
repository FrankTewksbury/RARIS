"""Widen authority_type column to VARCHAR(50) for v3 insurance types.

Revision ID: 004_widen_authority_type
Revises: 003_add_golden_runs
Create Date: 2026-03-09
"""

import sqlalchemy as sa
from alembic import op

revision = "004_widen_authority_type"
down_revision = "003_add_golden_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "regulatory_bodies",
        "authority_type",
        type_=sa.String(50),
        existing_type=sa.String(13),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "regulatory_bodies",
        "authority_type",
        type_=sa.String(13),
        existing_type=sa.String(50),
        existing_nullable=True,
    )
