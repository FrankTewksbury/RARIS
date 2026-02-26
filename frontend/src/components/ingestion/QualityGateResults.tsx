import { useDocument, useApproveDocument, useRejectDocument } from "../../hooks/useIngestion";

interface Props {
  documentId: string | undefined;
  ingestionId: string;
  onClose: () => void;
}

export function QualityGateResults({ documentId, ingestionId, onClose }: Props) {
  const { data: doc } = useDocument(documentId);
  const approveMutation = useApproveDocument(ingestionId);
  const rejectMutation = useRejectDocument(ingestionId);

  if (!documentId || !doc) {
    return null;
  }

  const gates = doc.quality_gates || {};

  return (
    <div className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Quality Gates — {doc.title || doc.document_id}</h3>
        <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>
          Close
        </button>
      </div>

      <table className="data-table" style={{ marginTop: "0.5rem" }}>
        <thead>
          <tr>
            <th>Gate</th>
            <th>Result</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(gates).map(([name, gate]) => (
            <tr key={name}>
              <td style={{ textTransform: "capitalize" }}>{name}</td>
              <td>
                <span className={`badge ${gate.passed ? "badge-success" : "badge-danger"}`}>
                  {gate.passed ? "PASS" : "FAIL"}
                </span>
              </td>
              <td className="text-muted">{gate.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: "0.75rem" }}>
        <strong>Curation Notes</strong>
        <ul style={{ marginTop: "0.25rem", paddingLeft: "1.25rem" }}>
          {(doc.curation_notes || []).map((note, i) => (
            <li key={i} className="text-muted" style={{ fontSize: "0.85rem" }}>
              {note}
            </li>
          ))}
        </ul>
      </div>

      <div style={{ marginTop: "0.75rem" }}>
        <strong>Metadata</strong>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.25rem 1rem", marginTop: "0.25rem", fontSize: "0.85rem" }}>
          <span className="text-muted">Jurisdiction:</span><span>{doc.jurisdiction}</span>
          <span className="text-muted">Regulatory Body:</span><span>{doc.regulatory_body}</span>
          <span className="text-muted">Authority Level:</span><span>{doc.authority_level}</span>
          <span className="text-muted">Document Type:</span><span>{doc.document_type}</span>
          <span className="text-muted">Effective Date:</span><span>{doc.effective_date || "—"}</span>
          <span className="text-muted">Quality Score:</span><span>{doc.quality_score.toFixed(2)}</span>
          <span className="text-muted">Sections:</span><span>{doc.section_count}</span>
          <span className="text-muted">Tables:</span><span>{doc.table_count}</span>
          <span className="text-muted">Chunks:</span><span>{doc.chunk_count}</span>
        </div>
      </div>

      {doc.status !== "indexed" && doc.status !== "rejected" && (
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
          <button
            className="btn-success"
            onClick={() => approveMutation.mutate(doc.document_id)}
            disabled={approveMutation.isPending}
          >
            Approve
          </button>
          <button
            className="btn-danger"
            onClick={() => rejectMutation.mutate({ docId: doc.document_id, reason: "Manual rejection" })}
            disabled={rejectMutation.isPending}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
