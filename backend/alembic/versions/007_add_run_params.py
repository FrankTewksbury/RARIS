"""Add run_params JSONB column to manifests for storing discovery run settings.

Revision ID: 007_add_run_params
Revises: 006_add_checkpoint_data
Create Date: 2026-03-11
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "007_add_run_params"
down_revision = "006_add_checkpoint_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manifests",
        sa.Column("run_params", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("manifests", "run_params")
