"""Add checkpoint_data JSONB column to manifests for BFS queue resume.

Revision ID: 006_add_checkpoint_data
Revises: 005_jurisdiction_code
Create Date: 2026-03-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "006_add_checkpoint_data"
down_revision = "005_jurisdiction_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manifests",
        sa.Column("checkpoint_data", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("manifests", "checkpoint_data")
