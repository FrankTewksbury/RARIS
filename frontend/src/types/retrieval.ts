export interface SearchFilters {
  jurisdiction?: string[];
  document_type?: string[];
  regulatory_body?: string[];
  authority_level?: string[];
  tags?: string[];
}

export interface Citation {
  chunk_id: string;
  chunk_text: string;
  section_path: string;
  document_id: string;
  document_title: string;
  source_id: string;
  source_url: string;
  regulatory_body: string;
  jurisdiction: string;
  authority_level: string;
  manifest_id: string;
  confidence: number;
}

export interface QueryRequest {
  query: string;
  depth: number;
  filters?: SearchFilters;
}

export interface QueryResponse {
  query_id: string;
  query: string;
  depth: number;
  depth_name: string;
  response_text: string;
  citations: Citation[];
  sources_count: number;
  token_count: number;
}

export interface Finding {
  category: string;
  severity: string;
  description: string;
  primary_citation: Record<string, unknown>;
  comparison_citation: Record<string, unknown> | null;
  recommendation: string;
}

export interface AnalysisRequest {
  analysis_type: string;
  primary_text: string;
  filters?: SearchFilters;
  depth: number;
}

export interface AnalysisResponse {
  analysis_id: string;
  analysis_type: string;
  findings: Finding[];
  summary: string;
  coverage_score: number | null;
  citations: Citation[];
}

export interface CorpusStats {
  total_documents: number;
  indexed_documents: number;
  total_chunks: number;
  indexed_chunks: number;
  by_jurisdiction: Record<string, number>;
  by_document_type: Record<string, number>;
  by_regulatory_body: Record<string, number>;
}

export interface CorpusSourceSummary {
  source_id: string;
  manifest_id: string;
  name: string;
  regulatory_body: string;
  jurisdiction: string;
  authority_level: string;
  document_type: string;
  document_count: number;
  chunk_count: number;
}

export const DEPTH_LEVELS = [
  { value: 1, name: "Quick Check", description: "Yes/no with top citation", budget: "~200 tokens" },
  { value: 2, name: "Summary", description: "Key points with citations", budget: "~500 tokens" },
  { value: 3, name: "Analysis", description: "Detailed analysis with full chains", budget: "~1500 tokens" },
  { value: 4, name: "Exhaustive", description: "Comprehensive regulatory audit", budget: "~4000 tokens" },
] as const;

export const ANALYSIS_TYPES = [
  { value: "gap", label: "Gap Analysis" },
  { value: "conflict", label: "Conflict Detection" },
  { value: "coverage", label: "Coverage Mapping" },
  { value: "change_impact", label: "Change Impact" },
] as const;

export interface QuerySSEEvent {
  event: string;
  data: {
    status?: string;
    token?: string;
    response?: string;
    citations?: Citation[];
    message?: string;
  };
}
