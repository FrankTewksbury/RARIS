import { useDocument } from "../../hooks/useIngestion";

interface Props {
  documentId: string | undefined;
  onClose: () => void;
}

export function DocumentViewer({ documentId, onClose }: Props) {
  const { data: doc } = useDocument(documentId);

  if (!documentId || !doc) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "800px", maxHeight: "80vh", overflow: "auto" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
          <h3>{doc.title || "Untitled Document"}</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1.2rem" }}>
            X
          </button>
        </div>

        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
          <span className={`badge badge-${doc.status === "indexed" ? "success" : doc.status === "rejected" ? "danger" : "primary"}`}>
            {doc.status}
          </span>
          <span className="badge">{doc.document_type}</span>
          <span className="badge">{doc.jurisdiction}</span>
          <span className="badge">{doc.authority_level}</span>
          {doc.effective_date && <span className="badge">{doc.effective_date}</span>}
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <strong>Tags:</strong>{" "}
          {(doc.classification_tags || []).map((tag, i) => (
            <span key={i} className="badge" style={{ marginRight: "0.25rem" }}>
              {tag}
            </span>
          ))}
        </div>

        {doc.cross_references.length > 0 && (
          <div style={{ marginBottom: "1rem" }}>
            <strong>Cross References:</strong>
            <ul style={{ paddingLeft: "1.25rem", marginTop: "0.25rem" }}>
              {doc.cross_references.map((ref, i) => (
                <li key={i} className="text-muted" style={{ fontSize: "0.85rem" }}>
                  {ref}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div style={{ marginBottom: "1rem" }}>
          <strong>Content Preview</strong>
          <pre
            style={{
              background: "var(--bg)",
              padding: "1rem",
              borderRadius: "var(--radius)",
              whiteSpace: "pre-wrap",
              fontSize: "0.8rem",
              maxHeight: "300px",
              overflow: "auto",
              marginTop: "0.25rem",
            }}
          >
            {doc.full_text_preview}
          </pre>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem", fontSize: "0.85rem" }}>
          <div className="panel" style={{ padding: "0.5rem", textAlign: "center" }}>
            <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{doc.section_count}</div>
            <div className="text-muted">Sections</div>
          </div>
          <div className="panel" style={{ padding: "0.5rem", textAlign: "center" }}>
            <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{doc.table_count}</div>
            <div className="text-muted">Tables</div>
          </div>
          <div className="panel" style={{ padding: "0.5rem", textAlign: "center" }}>
            <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{doc.chunk_count}</div>
            <div className="text-muted">Chunks</div>
          </div>
        </div>
      </div>
    </div>
  );
}
