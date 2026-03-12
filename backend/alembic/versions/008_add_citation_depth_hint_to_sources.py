"""Add citation and depth_hint columns to sources table.

Revision ID: 008_add_citation_depth_hint
Revises: 007_add_run_params
Create Date: 2026-03-11
"""
import sqlalchemy as sa
from alembic import op

revision = "008_add_citation_depth_hint"
down_revision = "007_add_run_params"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("citation", sa.Text, nullable=True))
    op.add_column("sources", sa.Column("depth_hint", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "citation")
    op.drop_column("sources", "depth_hint")
