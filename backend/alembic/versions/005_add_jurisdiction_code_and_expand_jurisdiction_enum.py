"""Add jurisdiction_code to regulatory_bodies; expand Jurisdiction enum with territorial/interstate.

Revision ID: 005_jurisdiction_code
Revises: 004_widen_authority_type
Create Date: 2026-03-09
"""

import sqlalchemy as sa
from alembic import op

revision = "005_jurisdiction_code"
down_revision = "004_widen_authority_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "regulatory_bodies",
        sa.Column("jurisdiction_code", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("regulatory_bodies", "jurisdiction_code")
