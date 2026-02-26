"""Initial schema — all 21 tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-02-25
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- Phase 1: Domain Discovery ---

    op.create_table(
        "manifests",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("domain", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_by", sa.String(100), default="domain-discovery-agent-v1"
        ),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("status", sa.String(30), default="generating"),
        sa.Column("completeness_score", sa.Float, default=0.0),
        sa.Column("jurisdiction_hierarchy", postgresql.JSONB, nullable=True),
        sa.Column("review_history", postgresql.JSONB, nullable=True),
    )

    op.create_table(
        "regulatory_bodies",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column(
            "manifest_id",
            sa.String(100),
            sa.ForeignKey("manifests.id"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("jurisdiction", sa.String(30)),
        sa.Column("authority_type", sa.String(30)),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("governs", postgresql.JSONB, nullable=True),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column(
            "manifest_id",
            sa.String(100),
            sa.ForeignKey("manifests.id"),
            primary_key=True,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("regulatory_body_id", sa.String(100), nullable=False),
        sa.Column("type", sa.String(30)),
        sa.Column("format", sa.String(30)),
        sa.Column("authority", sa.String(30)),
        sa.Column("jurisdiction", sa.String(30)),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("access_method", sa.String(20)),
        sa.Column("update_frequency", sa.String(50), nullable=True),
        sa.Column("last_known_update", sa.String(50), nullable=True),
        sa.Column("estimated_size", sa.String(20), nullable=True),
        sa.Column("scraping_notes", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, default=0.0),
        sa.Column("needs_human_review", sa.Boolean, default=False),
        sa.Column("review_notes", sa.Text, nullable=True),
        sa.Column("classification_tags", postgresql.JSONB, nullable=True),
        sa.Column("relationships", postgresql.JSONB, nullable=True),
    )

    op.create_table(
        "coverage_assessments",
        sa.Column(
            "manifest_id",
            sa.String(100),
            sa.ForeignKey("manifests.id"),
            primary_key=True,
        ),
        sa.Column("total_sources", sa.Integer, default=0),
        sa.Column("by_jurisdiction", postgresql.JSONB, nullable=True),
        sa.Column("by_type", postgresql.JSONB, nullable=True),
        sa.Column("completeness_score", sa.Float, default=0.0),
    )

    op.create_table(
        "known_gaps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "manifest_id",
            sa.String(100),
            sa.ForeignKey("coverage_assessments.manifest_id"),
        ),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20)),
        sa.Column("mitigation", sa.Text, nullable=True),
    )

    # --- Phase 2: Data Acquisition ---

    op.create_table(
        "acquisition_runs",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("manifest_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_sources", sa.Integer, default=0),
    )

    op.create_table(
        "acquisition_sources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "acquisition_id",
            sa.String(100),
            sa.ForeignKey("acquisition_runs.id"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("manifest_id", sa.String(100), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("regulatory_body", sa.String(100), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("access_method", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("staged_document_id", sa.String(100), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "staged_documents",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("manifest_id", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("acquisition_method", sa.String(20), nullable=False),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("raw_content_path", sa.Text, nullable=False),
        sa.Column("byte_size", sa.Integer, default=0),
        sa.Column("status", sa.String(30), default="staged"),
        sa.Column("provenance", postgresql.JSONB, nullable=True),
    )

    # --- Phase 3: Ingestion & Curation ---

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("acquisition_id", sa.String(100), nullable=False),
        sa.Column("manifest_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_documents", sa.Integer, default=0),
        sa.Column("processed", sa.Integer, default=0),
        sa.Column("failed", sa.Integer, default=0),
    )

    op.create_table(
        "internal_documents",
        sa.Column("id", sa.String(150), primary_key=True),
        sa.Column(
            "ingestion_run_id",
            sa.String(100),
            sa.ForeignKey("ingestion_runs.id"),
            nullable=False,
        ),
        sa.Column("manifest_id", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("staged_document_id", sa.String(100), nullable=False),
        sa.Column("title", sa.Text, server_default=""),
        sa.Column("full_text", sa.Text, server_default=""),
        sa.Column("jurisdiction", sa.String(50), server_default=""),
        sa.Column("regulatory_body", sa.String(100), server_default=""),
        sa.Column("effective_date", sa.String(50), nullable=True),
        sa.Column("authority_level", sa.String(30), server_default="informational"),
        sa.Column("document_type", sa.String(30), server_default="guidance"),
        sa.Column("applicability_scope", postgresql.JSONB, nullable=True),
        sa.Column("classification_tags", postgresql.JSONB, nullable=True),
        sa.Column("cross_references", postgresql.JSONB, nullable=True),
        sa.Column("supersedes", postgresql.JSONB, nullable=True),
        sa.Column("superseded_by", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(20), server_default="raw"),
        sa.Column("quality_score", sa.Float, default=0.0),
        sa.Column("quality_gates", postgresql.JSONB, nullable=True),
        sa.Column("curation_notes", postgresql.JSONB, nullable=True),
        sa.Column("curated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(80), server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "document_sections",
        sa.Column("id", sa.String(150), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(150),
            sa.ForeignKey("internal_documents.id"),
            nullable=False,
        ),
        sa.Column("parent_id", sa.String(150), nullable=True),
        sa.Column("heading", sa.Text, server_default=""),
        sa.Column("level", sa.Integer, default=1),
        sa.Column("text", sa.Text, server_default=""),
        sa.Column("position", sa.Integer, default=0),
    )

    op.create_table(
        "document_tables",
        sa.Column("id", sa.String(150), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(150),
            sa.ForeignKey("internal_documents.id"),
            nullable=False,
        ),
        sa.Column("section_id", sa.String(150), nullable=True),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("headers", postgresql.JSONB, nullable=True),
        sa.Column("rows", postgresql.JSONB, nullable=True),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(150),
            sa.ForeignKey("internal_documents.id"),
            nullable=False,
        ),
        sa.Column("section_id", sa.String(150), server_default=""),
        sa.Column("section_path", sa.Text, server_default=""),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, default=0),
        sa.Column("position", sa.Integer, default=0),
        sa.Column("cross_references", postgresql.JSONB, nullable=True),
        sa.Column("chunk_metadata", postgresql.JSONB, nullable=True),
    )

    # pgvector embedding column — added separately because op.create_table
    # does not natively support custom Vector type
    op.execute(
        "ALTER TABLE chunks ADD COLUMN embedding vector(3072)"
    )

    # tsvector for lexical search
    op.execute(
        "ALTER TABLE chunks ADD COLUMN search_vector tsvector"
    )

    # --- Phase 4: Retrieval ---

    op.create_table(
        "query_records",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("depth", sa.Integer, default=2),
        sa.Column("filters", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("response_text", sa.Text, server_default=""),
        sa.Column("citations", postgresql.JSONB, nullable=True),
        sa.Column("sources_count", sa.Integer, default=0),
        sa.Column("token_count", sa.Integer, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "analysis_records",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("analysis_type", sa.String(30), nullable=False),
        sa.Column("primary_text_preview", sa.Text, server_default=""),
        sa.Column("filters", postgresql.JSONB, nullable=True),
        sa.Column("depth", sa.Integer, default=3),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("findings", postgresql.JSONB, nullable=True),
        sa.Column("summary", sa.Text, server_default=""),
        sa.Column("coverage_score", sa.Float, nullable=True),
        sa.Column("citations", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Phase 5: Verticals ---

    op.create_table(
        "verticals",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain_description", sa.Text, nullable=False),
        sa.Column("scope", postgresql.JSONB, nullable=True),
        sa.Column("llm_provider", sa.String(50), server_default="openai"),
        sa.Column("expected_source_count_min", sa.Integer, default=100),
        sa.Column("expected_source_count_max", sa.Integer, default=300),
        sa.Column("coverage_target", sa.Float, default=0.85),
        sa.Column("rate_limit_ms", sa.Integer, default=2000),
        sa.Column("max_concurrent", sa.Integer, default=5),
        sa.Column("timeout_seconds", sa.Integer, default=120),
        sa.Column("phase", sa.String(30), server_default="created"),
        sa.Column("manifest_id", sa.String(100), nullable=True),
        sa.Column("acquisition_id", sa.String(100), nullable=True),
        sa.Column("ingestion_id", sa.String(100), nullable=True),
        sa.Column("source_count", sa.Integer, default=0),
        sa.Column("document_count", sa.Integer, default=0),
        sa.Column("chunk_count", sa.Integer, default=0),
        sa.Column("coverage_score", sa.Float, default=0.0),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- Phase 6: Feedback & Curation ---

    op.create_table(
        "response_feedback",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("query_id", sa.String(100), nullable=False),
        sa.Column("feedback_type", sa.String(20), nullable=False),
        sa.Column("citation_id", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("submitted_by", sa.String(100), server_default="anonymous"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("traced_source_id", sa.String(100), nullable=True),
        sa.Column("traced_manifest_id", sa.String(100), nullable=True),
        sa.Column("traced_document_id", sa.String(150), nullable=True),
        sa.Column("auto_action", sa.String(50), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "curation_queue",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("manifest_id", sa.String(100), nullable=False),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("reason", sa.Text, server_default=""),
        sa.Column("trigger_type", sa.String(30), server_default="feedback"),
        sa.Column("feedback_id", sa.String(100), nullable=True),
        sa.Column("change_event_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "change_events",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("manifest_id", sa.String(100), nullable=False),
        sa.Column("detection_method", sa.String(30), nullable=False),
        sa.Column("change_type", sa.String(30), nullable=False),
        sa.Column("previous_hash", sa.String(80), nullable=True),
        sa.Column("current_hash", sa.String(80), nullable=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("status", sa.String(20), server_default="detected"),
        sa.Column("impact_assessment", sa.Text, nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "accuracy_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_date",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("total_feedback", sa.Integer, default=0),
        sa.Column("correct_count", sa.Integer, default=0),
        sa.Column("inaccurate_count", sa.Integer, default=0),
        sa.Column("outdated_count", sa.Integer, default=0),
        sa.Column("incomplete_count", sa.Integer, default=0),
        sa.Column("irrelevant_count", sa.Integer, default=0),
        sa.Column("accuracy_score", sa.Float, default=0.0),
        sa.Column("resolution_rate", sa.Float, default=0.0),
        sa.Column("avg_confidence", sa.Float, default=0.0),
        sa.Column("stale_sources", sa.Integer, default=0),
        sa.Column("by_vertical", postgresql.JSONB, nullable=True),
    )

    # --- Phase 8: Auth ---

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("scope", sa.String(20), server_default="read"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Indexes ---

    op.create_index("ix_sources_manifest_id", "sources", ["manifest_id"])
    op.create_index("ix_regulatory_bodies_manifest_id", "regulatory_bodies", ["manifest_id"])
    op.create_index(
        "ix_acquisition_sources_acquisition_id", "acquisition_sources", ["acquisition_id"]
    )
    op.create_index(
        "ix_internal_documents_ingestion_run_id", "internal_documents", ["ingestion_run_id"]
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_response_feedback_query_id", "response_feedback", ["query_id"])
    op.create_index("ix_curation_queue_status", "curation_queue", ["status"])
    op.create_index("ix_change_events_source_id", "change_events", ["source_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # GIN index for tsvector lexical search
    op.execute(
        "CREATE INDEX ix_chunks_search_vector ON chunks USING GIN (search_vector)"
    )

    # HNSW index for vector similarity search
    op.execute(
        "CREATE INDEX ix_chunks_embedding ON chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    tables = [
        "api_keys",
        "accuracy_snapshots",
        "change_events",
        "curation_queue",
        "response_feedback",
        "verticals",
        "analysis_records",
        "query_records",
        "chunks",
        "document_tables",
        "document_sections",
        "internal_documents",
        "ingestion_runs",
        "staged_documents",
        "acquisition_sources",
        "acquisition_runs",
        "known_gaps",
        "coverage_assessments",
        "sources",
        "regulatory_bodies",
        "manifests",
    ]
    for table in tables:
        op.drop_table(table)

    op.execute("DROP EXTENSION IF EXISTS vector")
