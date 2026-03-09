"""Add logical runs and golden snapshot tables.

Revision ID: 003_add_golden_runs
Revises: 002_add_programs
Create Date: 2026-03-08
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "003_add_golden_runs"
down_revision = "002_add_programs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "golden_runs",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_run_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("accepted_by", sa.String(100), nullable=False, server_default="system"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("strategy", sa.String(50), nullable=False, server_default="pick_richest"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_golden_runs_domain", "golden_runs", ["domain"])

    op.create_table(
        "logical_runs",
        sa.Column("run_id", sa.String(100), primary_key=True),
        sa.Column("manifest_id", sa.String(100), sa.ForeignKey("manifests.id"), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="candidate"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "promoted_to_golden_run_id",
            sa.String(120),
            sa.ForeignKey("golden_runs.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_logical_runs_manifest_id", "logical_runs", ["manifest_id"], unique=True)
    op.create_index("ix_logical_runs_domain", "logical_runs", ["domain"])
    op.create_index(
        "ix_logical_runs_promoted_to_golden_run_id",
        "logical_runs",
        ["promoted_to_golden_run_id"],
    )

    op.create_table(
        "golden_run_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("golden_run_id", sa.String(120), sa.ForeignKey("golden_runs.id"), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("merge_key", sa.String(255), nullable=False),
        sa.Column("canonical_id", sa.String(255), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("administering_entity", sa.String(255), nullable=False),
        sa.Column("geo_scope", sa.String(20), nullable=False),
        sa.Column("jurisdiction", sa.String(120), nullable=True),
        sa.Column("benefits", sa.Text(), nullable=True),
        sa.Column("eligibility", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="verification_pending"),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_snippet", sa.Text(), nullable=True),
        sa.Column("source_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provenance_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("needs_human_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_run_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("found_by_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ensemble_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_golden_run_items_golden_run_id", "golden_run_items", ["golden_run_id"])
    op.create_index("ix_golden_run_items_domain", "golden_run_items", ["domain"])
    op.create_index("ix_golden_run_items_merge_key", "golden_run_items", ["merge_key"])

    op.create_table(
        "domain_current_golden",
        sa.Column("domain", sa.Text(), primary_key=True),
        sa.Column("golden_run_id", sa.String(120), sa.ForeignKey("golden_runs.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_domain_current_golden_golden_run_id",
        "domain_current_golden",
        ["golden_run_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_domain_current_golden_golden_run_id", table_name="domain_current_golden")
    op.drop_table("domain_current_golden")
    op.drop_index("ix_golden_run_items_merge_key", table_name="golden_run_items")
    op.drop_index("ix_golden_run_items_domain", table_name="golden_run_items")
    op.drop_index("ix_golden_run_items_golden_run_id", table_name="golden_run_items")
    op.drop_table("golden_run_items")
    op.drop_index(
        "ix_logical_runs_promoted_to_golden_run_id",
        table_name="logical_runs",
    )
    op.drop_index("ix_logical_runs_domain", table_name="logical_runs")
    op.drop_index("ix_logical_runs_manifest_id", table_name="logical_runs")
    op.drop_table("logical_runs")
    op.drop_index("ix_golden_runs_domain", table_name="golden_runs")
    op.drop_table("golden_runs")
