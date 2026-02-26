import type { Citation } from "../../types/retrieval";

interface Props {
  citation: Citation;
  onClose: () => void;
}

export function CitationExplorer({ citation, onClose }: Props) {
  return (
    <div className="panel" style={{ borderLeft: "3px solid var(--primary)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Citation Chain</h3>
        <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.2rem" }}>
          &times;
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {/* Chunk level */}
        <div>
          <div className="text-muted" style={{ fontSize: "0.75rem", marginBottom: "0.25rem" }}>
            CHUNK
          </div>
          <div style={{ fontSize: "0.85rem", fontFamily: "monospace" }}>{citation.chunk_id}</div>
          {citation.chunk_text && (
            <blockquote style={{
              margin: "0.5rem 0 0 0",
              paddingLeft: "0.75rem",
              borderLeft: "2px solid var(--border)",
              color: "var(--text-muted)",
              fontSize: "0.85rem",
              maxHeight: "150px",
              overflow: "auto",
            }}>
              {citation.chunk_text}
            </blockquote>
          )}
        </div>

        <div style={{ textAlign: "center", color: "var(--text-muted)" }}>&#x2193;</div>

        {/* Section level */}
        <div>
          <div className="text-muted" style={{ fontSize: "0.75rem", marginBottom: "0.25rem" }}>
            SECTION
          </div>
          <div style={{ fontWeight: 600 }}>{citation.section_path}</div>
        </div>

        <div style={{ textAlign: "center", color: "var(--text-muted)" }}>&#x2193;</div>

        {/* Document level */}
        <div>
          <div className="text-muted" style={{ fontSize: "0.75rem", marginBottom: "0.25rem" }}>
            DOCUMENT
          </div>
          <div style={{ fontWeight: 600 }}>{citation.document_title || citation.document_id}</div>
          <div className="text-muted" style={{ fontSize: "0.85rem" }}>ID: {citation.document_id}</div>
        </div>

        <div style={{ textAlign: "center", color: "var(--text-muted)" }}>&#x2193;</div>

        {/* Source level */}
        <div>
          <div className="text-muted" style={{ fontSize: "0.75rem", marginBottom: "0.25rem" }}>
            SOURCE
          </div>
          <div style={{ fontWeight: 600 }}>{citation.source_id}</div>
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem", flexWrap: "wrap" }}>
            <span className="badge">{citation.regulatory_body}</span>
            <span className="badge">{citation.jurisdiction}</span>
            <span className={`badge ${citation.authority_level === "binding" ? "badge-danger" : ""}`}>
              {citation.authority_level}
            </span>
          </div>
          {citation.source_url && (
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: "0.85rem", marginTop: "0.25rem", display: "block" }}
            >
              View original source
            </a>
          )}
        </div>

        <div style={{ textAlign: "center", color: "var(--text-muted)" }}>&#x2193;</div>

        {/* Manifest level */}
        <div>
          <div className="text-muted" style={{ fontSize: "0.75rem", marginBottom: "0.25rem" }}>
            MANIFEST
          </div>
          <div style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>{citation.manifest_id}</div>
          <div className="text-muted" style={{ fontSize: "0.85rem" }}>
            Confidence: {(citation.confidence * 100).toFixed(0)}%
          </div>
        </div>
      </div>
    </div>
  );
}
