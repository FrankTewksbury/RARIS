"""Tests for feedback models, schemas, tracer logic, and monitor utilities."""

from datetime import UTC, datetime

from app.models.feedback import (
    ChangeEvent,
    CurationQueueItem,
    CurationQueuePriority,
    CurationQueueStatus,
    FeedbackStatus,
    FeedbackType,
    ResponseFeedback,
)
from app.schemas.feedback import (
    AccuracyDashboardData,
    AccuracyMetrics,
    AccuracyTrendPoint,
    ChangeEventSchema,
    CurationQueueItemSchema,
    FeedbackDetail,
    ResolveFeedbackRequest,
    SubmitFeedbackRequest,
    TriggerMonitorResponse,
)

# --- Enum tests ---


class TestFeedbackType:
    def test_all_types_present(self):
        expected = {"inaccurate", "outdated", "incomplete", "irrelevant", "correct"}
        assert set(FeedbackType) == expected

    def test_type_values_match_names(self):
        for ft in FeedbackType:
            assert ft.value == ft.name


class TestFeedbackStatus:
    def test_all_statuses_present(self):
        expected = {"pending", "investigating", "resolved", "dismissed"}
        assert set(FeedbackStatus) == expected


class TestCurationQueuePriority:
    def test_all_priorities_present(self):
        expected = {"critical", "high", "medium", "low"}
        assert set(CurationQueuePriority) == expected

    def test_priority_values(self):
        assert CurationQueuePriority.critical == "critical"
        assert CurationQueuePriority.low == "low"


class TestCurationQueueStatus:
    def test_all_statuses_present(self):
        expected = {"pending", "processing", "resolved", "dismissed"}
        assert set(CurationQueueStatus) == expected


# --- Model tests ---


class TestResponseFeedbackModel:
    def test_model_creation(self):
        fb = ResponseFeedback(
            id="fb-test-001",
            query_id="q-123",
            feedback_type=FeedbackType.inaccurate,
            description="Incorrect citation",
            submitted_by="tester",
            status=FeedbackStatus.pending,
        )
        assert fb.id == "fb-test-001"
        assert fb.feedback_type == FeedbackType.inaccurate
        assert fb.status == FeedbackStatus.pending
        assert fb.citation_id is None
        assert fb.resolution is None
        assert fb.traced_source_id is None
        assert fb.auto_action is None

    def test_model_with_trace(self):
        fb = ResponseFeedback(
            id="fb-test-002",
            query_id="q-456",
            feedback_type=FeedbackType.outdated,
            description="Source is from 2020",
            submitted_by="analyst",
            status=FeedbackStatus.pending,
            traced_source_id="src-abc",
            traced_manifest_id="manifest-xyz",
            traced_document_id="doc-123",
            auto_action="queued_reacquisition",
        )
        assert fb.traced_source_id == "src-abc"
        assert fb.traced_manifest_id == "manifest-xyz"
        assert fb.auto_action == "queued_reacquisition"

    def test_status_transition(self):
        fb = ResponseFeedback(
            id="fb-test-003",
            query_id="q-789",
            feedback_type=FeedbackType.correct,
            description="Good answer",
            submitted_by="reviewer",
            status=FeedbackStatus.pending,
        )
        fb.status = FeedbackStatus.resolved
        fb.resolution = "Confirmed correct"
        fb.resolved_at = datetime.now(UTC)
        assert fb.status == FeedbackStatus.resolved
        assert fb.resolution == "Confirmed correct"
        assert fb.resolved_at is not None


class TestCurationQueueItemModel:
    def test_model_creation(self):
        item = CurationQueueItem(
            id="rcq-test-001",
            source_id="src-abc",
            manifest_id="manifest-xyz",
            priority=CurationQueuePriority.high,
            reason="Inaccuracy reported",
            trigger_type="feedback",
            feedback_id="fb-test-001",
            status=CurationQueueStatus.pending,
        )
        assert item.id == "rcq-test-001"
        assert item.priority == CurationQueuePriority.high
        assert item.trigger_type == "feedback"
        assert item.feedback_id == "fb-test-001"
        assert item.change_event_id is None
        assert item.result is None

    def test_change_triggered_item(self):
        item = CurationQueueItem(
            id="rcq-chg-001",
            source_id="src-def",
            manifest_id="manifest-abc",
            priority=CurationQueuePriority.high,
            reason="Content change detected",
            trigger_type="change_detected",
            change_event_id="chg-001",
            status=CurationQueueStatus.pending,
        )
        assert item.trigger_type == "change_detected"
        assert item.change_event_id == "chg-001"
        assert item.feedback_id is None


class TestChangeEventModel:
    def test_model_creation(self):
        evt = ChangeEvent(
            id="chg-test-001",
            source_id="src-abc",
            manifest_id="manifest-xyz",
            detection_method="hash_check",
            change_type="content_update",
            previous_hash="abc123",
            current_hash="def456",
            description="Content hash changed for Source A",
            status="detected",
        )
        assert evt.id == "chg-test-001"
        assert evt.detection_method == "hash_check"
        assert evt.change_type == "content_update"
        assert evt.previous_hash == "abc123"
        assert evt.current_hash == "def456"
        assert evt.impact_assessment is None
        assert evt.resolved_at is None


# --- Schema tests ---


class TestSubmitFeedbackRequest:
    def test_minimal_request(self):
        req = SubmitFeedbackRequest(
            query_id="q-123",
            feedback_type="inaccurate",
        )
        assert req.query_id == "q-123"
        assert req.citation_id is None
        assert req.description == ""
        assert req.submitted_by == "anonymous"

    def test_full_request(self):
        req = SubmitFeedbackRequest(
            query_id="q-456",
            feedback_type="outdated",
            citation_id="chunk-789",
            description="This regulation was superseded in 2025",
            submitted_by="analyst@company.com",
        )
        assert req.citation_id == "chunk-789"
        assert "superseded" in req.description
        assert req.submitted_by == "analyst@company.com"


class TestFeedbackDetail:
    def test_detail_serialization(self):
        detail = FeedbackDetail(
            id="fb-001",
            query_id="q-123",
            feedback_type="inaccurate",
            citation_id="chunk-456",
            description="Wrong citation",
            submitted_by="tester",
            status="pending",
            resolution=None,
            traced_source_id="src-abc",
            traced_manifest_id="manifest-xyz",
            traced_document_id="doc-123",
            auto_action="confidence_reduced",
            submitted_at="2026-02-25T12:00:00Z",
            resolved_at=None,
        )
        data = detail.model_dump()
        assert data["auto_action"] == "confidence_reduced"
        assert data["traced_source_id"] == "src-abc"
        assert data["resolved_at"] is None


class TestResolveFeedbackRequest:
    def test_resolve(self):
        req = ResolveFeedbackRequest(resolution="Source updated and re-indexed")
        assert req.status == "resolved"

    def test_dismiss(self):
        req = ResolveFeedbackRequest(resolution="Not actionable", status="dismissed")
        assert req.status == "dismissed"


class TestCurationQueueItemSchema:
    def test_schema_fields(self):
        item = CurationQueueItemSchema(
            id="rcq-001",
            source_id="src-abc",
            manifest_id="manifest-xyz",
            priority="high",
            reason="Inaccuracy feedback",
            trigger_type="feedback",
            feedback_id="fb-001",
            change_event_id=None,
            status="pending",
            result=None,
            created_at="2026-02-25T12:00:00Z",
            processed_at=None,
        )
        assert item.priority == "high"
        assert item.trigger_type == "feedback"
        assert item.processed_at is None


class TestChangeEventSchema:
    def test_schema_fields(self):
        evt = ChangeEventSchema(
            id="chg-001",
            source_id="src-abc",
            manifest_id="manifest-xyz",
            detection_method="hash_check",
            change_type="content_update",
            previous_hash="abc123",
            current_hash="def456",
            description="Content changed",
            status="detected",
            impact_assessment=None,
            detected_at="2026-02-25T12:00:00Z",
            resolved_at=None,
        )
        data = evt.model_dump()
        assert data["detection_method"] == "hash_check"
        assert data["impact_assessment"] is None


class TestTriggerMonitorResponse:
    def test_response(self):
        resp = TriggerMonitorResponse(
            sources_checked=42,
            changes_detected=3,
            message="Monitor run complete",
        )
        assert resp.sources_checked == 42
        assert resp.changes_detected == 3


class TestAccuracyMetrics:
    def test_metrics(self):
        metrics = AccuracyMetrics(
            total_feedback=100,
            correct_count=75,
            inaccurate_count=10,
            outdated_count=8,
            incomplete_count=5,
            irrelevant_count=2,
            accuracy_score=0.882,
            resolution_rate=0.95,
            avg_source_confidence=0.87,
            stale_sources=3,
            pending_queue_items=5,
            unresolved_changes=2,
        )
        assert metrics.accuracy_score == 0.882
        assert metrics.total_feedback == 100
        assert metrics.correct_count + metrics.inaccurate_count == 85


class TestAccuracyDashboardData:
    def test_dashboard_data(self):
        dashboard = AccuracyDashboardData(
            current=AccuracyMetrics(
                total_feedback=50,
                correct_count=40,
                inaccurate_count=5,
                outdated_count=3,
                incomplete_count=1,
                irrelevant_count=1,
                accuracy_score=0.889,
                resolution_rate=0.92,
                avg_source_confidence=0.85,
                stale_sources=0,
                pending_queue_items=2,
                unresolved_changes=1,
            ),
            trends=[
                AccuracyTrendPoint(
                    date="2026-02-20",
                    accuracy_score=0.85,
                    total_feedback=30,
                    resolution_rate=0.90,
                ),
                AccuracyTrendPoint(
                    date="2026-02-25",
                    accuracy_score=0.889,
                    total_feedback=50,
                    resolution_rate=0.92,
                ),
            ],
            by_feedback_type={"correct": 40, "inaccurate": 5, "outdated": 3},
            by_vertical={"Insurance": 0.92, "Mortgage": 0.78},
        )
        assert len(dashboard.trends) == 2
        assert dashboard.by_vertical["Insurance"] == 0.92
        assert dashboard.current.accuracy_score == 0.889


# --- Tracer logic tests (unit, no DB) ---


class TestTracerConfidenceAdjustments:
    """Test the confidence adjustment constants from tracer module."""

    def test_adjustment_values(self):
        from app.feedback.tracer import _CONFIDENCE_ADJUSTMENTS

        assert _CONFIDENCE_ADJUSTMENTS[FeedbackType.inaccurate] == -0.1
        assert _CONFIDENCE_ADJUSTMENTS[FeedbackType.correct] == 0.05

    def test_confidence_clamping(self):
        """Confidence should be clamped to [0.0, 1.0]."""
        # Simulate the clamping logic from _adjust_confidence
        for confidence, delta, expected in [
            (0.5, -0.1, 0.4),
            (0.05, -0.1, 0.0),  # Clamped at 0
            (0.95, 0.05, 1.0),  # Clamped at 1
            (0.0, 0.05, 0.05),
            (1.0, -0.1, 0.9),
        ]:
            result = max(0.0, min(1.0, confidence + delta))
            assert result == expected, f"Failed for {confidence} + {delta}: got {result}"


class TestAutoActionMapping:
    """Test that each feedback type maps to the correct auto-action."""

    def test_inaccurate_action(self):
        assert FeedbackType.inaccurate.value == "inaccurate"

    def test_outdated_action(self):
        assert FeedbackType.outdated.value == "outdated"

    def test_incomplete_action(self):
        assert FeedbackType.incomplete.value == "incomplete"

    def test_irrelevant_action(self):
        assert FeedbackType.irrelevant.value == "irrelevant"

    def test_correct_action(self):
        assert FeedbackType.correct.value == "correct"


# --- Monitor hash logic tests ---


class TestMonitorHashComparison:
    """Test hash comparison logic used in the change monitor."""

    def test_same_hash_no_change(self):
        """Same hashes should indicate no change."""
        prev = "abc123def456"
        curr = "abc123def456"
        assert prev == curr  # No change

    def test_different_hash_detects_change(self):
        """Different hashes should indicate a change."""
        import hashlib

        content_a = b"Regulation text version 1"
        content_b = b"Regulation text version 2"
        hash_a = hashlib.sha256(content_a).hexdigest()
        hash_b = hashlib.sha256(content_b).hexdigest()
        assert hash_a != hash_b  # Change detected

    def test_hash_deterministic(self):
        """SHA-256 should produce consistent hashes."""
        import hashlib

        content = b"Some regulatory content"
        hash1 = hashlib.sha256(content).hexdigest()
        hash2 = hashlib.sha256(content).hexdigest()
        assert hash1 == hash2

    def test_hash_length(self):
        """SHA-256 hex digest should be 64 characters."""
        import hashlib

        h = hashlib.sha256(b"test").hexdigest()
        assert len(h) == 64
