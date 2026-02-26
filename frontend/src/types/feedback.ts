export interface SubmitFeedbackRequest {
  query_id: string;
  feedback_type: string;
  citation_id?: string;
  description?: string;
  submitted_by?: string;
}

export interface FeedbackDetail {
  id: string;
  query_id: string;
  feedback_type: string;
  citation_id: string | null;
  description: string;
  submitted_by: string;
  status: string;
  resolution: string | null;
  traced_source_id: string | null;
  traced_manifest_id: string | null;
  traced_document_id: string | null;
  auto_action: string | null;
  submitted_at: string;
  resolved_at: string | null;
}

export interface ResolveFeedbackRequest {
  resolution: string;
  status?: string;
}

export interface CurationQueueItem {
  id: string;
  source_id: string;
  manifest_id: string;
  priority: string;
  reason: string;
  trigger_type: string;
  feedback_id: string | null;
  change_event_id: string | null;
  status: string;
  result: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface ChangeEvent {
  id: string;
  source_id: string;
  manifest_id: string;
  detection_method: string;
  change_type: string;
  previous_hash: string | null;
  current_hash: string | null;
  description: string;
  status: string;
  impact_assessment: string | null;
  detected_at: string;
  resolved_at: string | null;
}

export interface TriggerMonitorResponse {
  sources_checked: number;
  changes_detected: number;
  message: string;
}

export interface AccuracyMetrics {
  total_feedback: number;
  correct_count: number;
  inaccurate_count: number;
  outdated_count: number;
  incomplete_count: number;
  irrelevant_count: number;
  accuracy_score: number;
  resolution_rate: number;
  avg_source_confidence: number;
  stale_sources: number;
  pending_queue_items: number;
  unresolved_changes: number;
}

export interface AccuracyTrendPoint {
  date: string;
  accuracy_score: number;
  total_feedback: number;
  resolution_rate: number;
}

export interface AccuracyDashboardData {
  current: AccuracyMetrics;
  trends: AccuracyTrendPoint[];
  by_feedback_type: Record<string, number>;
  by_vertical: Record<string, number>;
}

export const FEEDBACK_TYPES = [
  { value: "inaccurate", label: "Inaccurate", color: "#ef4444" },
  { value: "outdated", label: "Outdated", color: "#eab308" },
  { value: "incomplete", label: "Incomplete", color: "#f97316" },
  { value: "irrelevant", label: "Irrelevant", color: "#8b5cf6" },
  { value: "correct", label: "Correct", color: "#22c55e" },
] as const;

export const PRIORITY_COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#3b82f6",
};

export const STATUS_COLORS: Record<string, string> = {
  pending: "#eab308",
  investigating: "#3b82f6",
  processing: "#3b82f6",
  resolved: "#22c55e",
  dismissed: "#6b7280",
  detected: "#ef4444",
};
