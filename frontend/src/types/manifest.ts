export interface Source {
  id: string;
  name: string;
  regulatory_body: string;
  type: SourceType;
  format: SourceFormat;
  authority: AuthorityLevel;
  jurisdiction: Jurisdiction;
  url: string;
  access_method: AccessMethod;
  update_frequency?: string;
  last_known_update?: string;
  estimated_size?: string;
  scraping_notes?: string;
  confidence: number;
  needs_human_review: boolean;
  review_notes?: string;
  classification_tags: string[];
  relationships: Record<string, unknown>;
}

export interface RegulatoryBody {
  id: string;
  name: string;
  jurisdiction: Jurisdiction;
  authority_type: string;
  url: string;
  governs: string[];
}

export interface CoverageAssessment {
  total_sources: number;
  by_jurisdiction: Record<string, number>;
  by_type: Record<string, number>;
  completeness_score: number;
  known_gaps: KnownGap[];
}

export interface KnownGap {
  description: string;
  severity: "high" | "medium" | "low";
  mitigation: string;
}

export interface ManifestSummary {
  id: string;
  domain: string;
  status: ManifestStatus;
  created: string;
  sources_count: number;
  programs_count: number;
  coverage_score: number;
}

export interface Program {
  id: string;
  canonical_id: string;
  name: string;
  administering_entity: string;
  geo_scope: "national" | "state" | "county" | "city" | "tribal";
  jurisdiction?: string;
  benefits?: string;
  eligibility?: string;
  status: "active" | "paused" | "closed" | "verification_pending";
  last_verified?: string;
  evidence_snippet?: string;
  source_urls: string[];
  provenance_links: Record<string, unknown>;
  confidence: number;
  needs_human_review: boolean;
}

export interface ManifestDetail extends ManifestSummary {
  sources: Source[];
  programs: Program[];
  domain_map: {
    regulatory_bodies: RegulatoryBody[];
    jurisdiction_hierarchy: unknown;
  };
  coverage_assessment: CoverageAssessment | null;
}

export interface GenerateRequest {
  domain_description: string;
  llm_provider: string;
  k_depth?: number;
  geo_scope?: "national" | "state" | "municipal";
  target_segments?: string[];
}

export interface GenerateResponse {
  manifest_id: string;
  status: string;
  stream_url: string;
}

export interface ReviewRequest {
  reviewer: string;
  notes: string;
}

export interface AgentStepEvent {
  step: string;
  status: string;
  message?: string;
  bodies_found?: number;
  sources_found?: number;
  relationships_mapped?: number;
  completeness_score?: number;
  bodies_processed?: number;
  total_bodies?: number;
  manifest_id?: string;
  total_sources?: number;
  coverage_score?: number;
}

export interface AgentProgressEvent {
  sources_found: number;
  bodies_processed: number;
  total_bodies: number;
}

export type ManifestStatus = "generating" | "pending_review" | "approved" | "active" | "archived";
export type SourceType = "statute" | "regulation" | "guidance" | "standard" | "educational" | "guide";
export type SourceFormat = "html" | "pdf" | "legal_xml" | "api" | "structured_data";
export type AuthorityLevel = "binding" | "advisory" | "informational";
export type Jurisdiction = "federal" | "state" | "municipal";
export type AccessMethod = "scrape" | "download" | "api" | "manual";
