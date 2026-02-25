export interface AcquisitionRunSummary {
  acquisition_id: string;
  manifest_id: string;
  status: AcquisitionStatus;
  started_at: string;
  total_sources: number;
  completed: number;
  failed: number;
}

export interface AcquisitionRunDetail extends AcquisitionRunSummary {
  elapsed_seconds: number;
  pending: number;
  retrying: number;
}

export interface AcquisitionSourceStatus {
  source_id: string;
  name: string;
  regulatory_body: string;
  access_method: string;
  status: SourceAcqStatus;
  duration_ms: number | null;
  staged_document_id: string | null;
  error: string | null;
  retry_count: number;
}

export interface StartAcquisitionResponse {
  acquisition_id: string;
  manifest_id: string;
  status: string;
  total_sources: number;
  stream_url: string;
}

export interface AcqSSEEvent {
  source_id?: string;
  name?: string;
  method?: string;
  staged_id?: string;
  duration_ms?: number;
  byte_size?: number;
  error?: string;
  retry_count?: number;
  completed?: number;
  failed?: number;
  pending?: number;
  retrying?: number;
  total?: number;
  message?: string;
}

export type AcquisitionStatus = "pending" | "running" | "complete" | "failed" | "cancelled";
export type SourceAcqStatus = "pending" | "running" | "complete" | "failed" | "retrying" | "skipped";
