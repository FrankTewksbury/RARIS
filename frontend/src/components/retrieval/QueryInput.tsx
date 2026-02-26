import { useState } from "react";
import { DEPTH_LEVELS } from "../../types/retrieval";
import type { SearchFilters } from "../../types/retrieval";

interface Props {
  onSubmit: (query: string, depth: number, filters?: SearchFilters) => void;
  isLoading: boolean;
  isStreaming: boolean;
  onCancel?: () => void;
}

export function QueryInput({ onSubmit, isLoading, isStreaming, onCancel }: Props) {
  const [query, setQuery] = useState("");
  const [depth, setDepth] = useState(2);
  const [showFilters, setShowFilters] = useState(false);
  const [jurisdiction, setJurisdiction] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [regulatoryBody, setRegulatoryBody] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    const filters: SearchFilters = {};
    if (jurisdiction) filters.jurisdiction = jurisdiction.split(",").map((s) => s.trim());
    if (documentType) filters.document_type = documentType.split(",").map((s) => s.trim());
    if (regulatoryBody) filters.regulatory_body = regulatoryBody.split(",").map((s) => s.trim());

    const hasFilters = Object.keys(filters).length > 0;
    onSubmit(query, depth, hasFilters ? filters : undefined);
  };

  return (
    <div className="panel">
      <h3>Query</h3>
      <form onSubmit={handleSubmit}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a regulatory question..."
          rows={3}
          style={{ width: "100%", marginBottom: "0.75rem", resize: "vertical" }}
          disabled={isStreaming}
        />

        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.75rem" }}>
          <label style={{ fontWeight: 600, minWidth: "50px" }}>Depth:</label>
          {DEPTH_LEVELS.map((level) => (
            <button
              key={level.value}
              type="button"
              className={`badge ${depth === level.value ? "badge-primary" : ""}`}
              onClick={() => setDepth(level.value)}
              title={`${level.description} (${level.budget})`}
              style={{ cursor: "pointer" }}
            >
              {level.value}. {level.name}
            </button>
          ))}
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            style={{ background: "none", border: "none", color: "var(--primary)", cursor: "pointer", padding: 0 }}
          >
            {showFilters ? "Hide filters" : "Show filters"}
          </button>

          {showFilters && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem", marginTop: "0.5rem" }}>
              <input
                placeholder="Jurisdiction (comma-sep)"
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value)}
              />
              <input
                placeholder="Document type (comma-sep)"
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
              />
              <input
                placeholder="Regulatory body (comma-sep)"
                value={regulatoryBody}
                onChange={(e) => setRegulatoryBody(e.target.value)}
              />
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button type="submit" disabled={!query.trim() || isLoading || isStreaming}>
            {isLoading ? "Querying..." : isStreaming ? "Streaming..." : "Ask"}
          </button>
          {isStreaming && onCancel && (
            <button type="button" onClick={onCancel} className="btn-danger">
              Cancel
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
