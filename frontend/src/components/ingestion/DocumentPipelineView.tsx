import type { DocumentSummary } from "../../types/ingestion";
import { useIngestionDocuments } from "../../hooks/useIngestion";

interface Props {
  ingestionId: string | undefined;
  onSelectDocument: (docId: string) => void;
}

const STATUS_ORDER = ["raw", "enriched", "validated", "approved", "indexed", "rejected"];

const STATUS_COLORS: Record<string, string> = {
  raw: "var(--text-muted)",
  enriched: "var(--warning)",
  validated: "var(--primary)",
  approved: "var(--success)",
  indexed: "#10b981",
  rejected: "var(--danger)",
};

export function DocumentPipelineView({ ingestionId, onSelectDocument }: Props) {
  const { data: documents } = useIngestionDocuments(ingestionId);

  if (!ingestionId || !documents) {
    return (
      <div className="panel">
        <h3>Document Pipeline</h3>
        <p className="text-muted">Start an ingestion run to see documents.</p>
      </div>
    );
  }

  const grouped = STATUS_ORDER.reduce<Record<string, DocumentSummary[]>>((acc, status) => {
    acc[status] = documents.filter((d: DocumentSummary) => d.status === status);
    return acc;
  }, {});

  return (
    <div className="panel">
      <h3>Document Pipeline</h3>
      <div style={{ display: "flex", gap: "0.75rem", overflowX: "auto" }}>
        {STATUS_ORDER.map((status) => (
          <div
            key={status}
            style={{
              flex: "1 0 160px",
              border: `1px solid var(--border)`,
              borderRadius: "var(--radius)",
              padding: "0.5rem",
              minHeight: "200px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: "0.5rem",
                borderBottom: `2px solid ${STATUS_COLORS[status] || "var(--border)"}`,
                paddingBottom: "0.25rem",
              }}
            >
              <strong style={{ textTransform: "capitalize" }}>{status}</strong>
              <span className="text-muted">{grouped[status]?.length || 0}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              {(grouped[status] || []).map((doc: DocumentSummary) => (
                <div
                  key={doc.document_id}
                  className="doc-card"
                  onClick={() => onSelectDocument(doc.document_id)}
                  style={{
                    padding: "0.4rem",
                    background: "var(--bg)",
                    borderRadius: "4px",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                  }}
                >
                  <div style={{ fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {doc.title || doc.source_id}
                  </div>
                  <div className="text-muted" style={{ fontSize: "0.7rem" }}>
                    {doc.document_type} · Q:{doc.quality_score.toFixed(2)}
                    {doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
