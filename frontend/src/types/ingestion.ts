export interface IngestionRunSummary {
  ingestion_id: string;
  acquisition_id: string;
  manifest_id: string;
  status: string;
  started_at: string;
  total_documents: number;
  processed: number;
  failed: number;
}

export interface IngestionRunDetail {
  ingestion_id: string;
  acquisition_id: string;
  manifest_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  total_documents: number;
  processed: number;
  failed: number;
}

export interface StartIngestionResponse {
  ingestion_id: string;
  acquisition_id: string;
  manifest_id: string;
  status: string;
  total_documents: number;
  stream_url: string;
}

export interface DocumentSummary {
  document_id: string;
  source_id: string;
  title: string;
  status: string;
  quality_score: number;
  document_type: string;
  jurisdiction: string;
  regulatory_body: string;
  chunk_count: number;
}

export interface DocumentDetail {
  document_id: string;
  source_id: string;
  staged_document_id: string;
  manifest_id: string;
  title: string;
  full_text_preview: string;
  status: string;
  quality_score: number;
  quality_gates: Record<string, { passed: boolean; detail: string }>;
  curation_notes: string[];
  effective_date: string | null;
  jurisdiction: string;
  regulatory_body: string;
  authority_level: string;
  document_type: string;
  classification_tags: string[];
  cross_references: string[];
  section_count: number;
  table_count: number;
  chunk_count: number;
  created_at: string;
  curated_at: string | null;
}

export interface IndexStats {
  total_chunks: number;
  indexed_chunks: number;
  total_documents: number;
  indexed_documents: number;
  by_jurisdiction: Record<string, number>;
  by_document_type: Record<string, number>;
}

export interface IngestionSSEEvent {
  event: string;
  source_id?: string;
  name?: string;
  status?: string;
  quality_score?: number;
  processed?: number;
  failed?: number;
  total?: number;
  error?: string;
  chunks_indexed?: number;
  run_id?: string;
  total_documents?: number;
  message?: string;
}
