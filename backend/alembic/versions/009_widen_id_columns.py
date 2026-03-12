"""Widen id columns to VARCHAR(255) to prevent truncation on deep k=3 compound IDs.

Revision ID: 009_widen_id_columns
Revises: 008_add_citation_depth_hint
Create Date: 2026-03-12
"""
import sqlalchemy as sa
from alembic import op

revision = "009_widen_id_columns"
down_revision = "008_add_citation_depth_hint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("sources", "id", type_=sa.String(255), existing_type=sa.String(100))
    op.alter_column("sources", "regulatory_body_id", type_=sa.String(255), existing_type=sa.String(100))
    op.alter_column("sources", "manifest_id", type_=sa.String(255), existing_type=sa.String(100))
    op.alter_column("regulatory_bodies", "id", type_=sa.String(255), existing_type=sa.String(100))
    op.alter_column("regulatory_bodies", "manifest_id", type_=sa.String(255), existing_type=sa.String(100))


def downgrade() -> None:
    op.alter_column("regulatory_bodies", "manifest_id", type_=sa.String(100), existing_type=sa.String(255))
    op.alter_column("regulatory_bodies", "id", type_=sa.String(100), existing_type=sa.String(255))
    op.alter_column("sources", "manifest_id", type_=sa.String(100), existing_type=sa.String(255))
    op.alter_column("sources", "regulatory_body_id", type_=sa.String(100), existing_type=sa.String(255))
    op.alter_column("sources", "id", type_=sa.String(100), existing_type=sa.String(255))
