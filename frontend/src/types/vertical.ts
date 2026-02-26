export interface ScopeConfig {
  jurisdictions: string[];
  regulatory_bodies: string[];
  lines_of_business: string[];
  exclusions: string[];
}

export interface CreateVerticalRequest {
  name: string;
  domain_description: string;
  scope: ScopeConfig;
  llm_provider: string;
  expected_source_count_min: number;
  expected_source_count_max: number;
  coverage_target: number;
  rate_limit_ms: number;
  max_concurrent: number;
  timeout_seconds: number;
}

export interface VerticalSummary {
  id: string;
  name: string;
  domain_description: string;
  phase: PipelinePhase;
  source_count: number;
  document_count: number;
  chunk_count: number;
  coverage_score: number;
  created_at: string;
  updated_at: string;
}

export interface PipelinePhaseStatus {
  phase: string;
  status: "pending" | "running" | "complete" | "failed";
  resource_id: string | null;
}

export interface VerticalDetail extends VerticalSummary {
  scope: ScopeConfig;
  llm_provider: string;
  expected_source_count_min: number;
  expected_source_count_max: number;
  coverage_target: number;
  rate_limit_ms: number;
  max_concurrent: number;
  timeout_seconds: number;
  manifest_id: string | null;
  acquisition_id: string | null;
  ingestion_id: string | null;
  last_error: string | null;
  pipeline_status: PipelinePhaseStatus[];
}

export interface VerticalPipelineStatus {
  vertical_id: string;
  phase: PipelinePhase;
  phases: PipelinePhaseStatus[];
  source_count: number;
  document_count: number;
  chunk_count: number;
  coverage_score: number;
}

export interface TriggerResponse {
  vertical_id: string;
  phase: string;
  resource_id: string;
  message: string;
}

export type PipelinePhase =
  | "created"
  | "discovering"
  | "discovered"
  | "acquiring"
  | "acquired"
  | "ingesting"
  | "indexed"
  | "failed";

export const PHASE_LABELS: Record<string, string> = {
  created: "Created",
  discovering: "Discovering",
  discovered: "Discovered",
  acquiring: "Acquiring",
  acquired: "Acquired",
  ingesting: "Ingesting",
  indexed: "Indexed",
  failed: "Failed",
};

export const PHASE_COLORS: Record<string, string> = {
  pending: "var(--text-muted)",
  running: "var(--primary)",
  complete: "var(--success)",
  failed: "var(--danger, #ef4444)",
};
