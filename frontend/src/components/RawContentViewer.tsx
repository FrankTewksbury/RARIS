import type { AcquisitionSourceStatus } from "../types/acquisition";

interface Props {
  source: AcquisitionSourceStatus;
  onClose: () => void;
}

export function RawContentViewer({ source, onClose }: Props) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal raw-content-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Staged Document — {source.name}</h3>

        <div className="metadata-grid">
          <div className="meta-item">
            <span className="label">Source ID</span>
            <span className="value">{source.source_id}</span>
          </div>
          <div className="meta-item">
            <span className="label">Staged ID</span>
            <span className="value">{source.staged_document_id || "—"}</span>
          </div>
          <div className="meta-item">
            <span className="label">Method</span>
            <span className="value">{source.access_method}</span>
          </div>
          <div className="meta-item">
            <span className="label">Duration</span>
            <span className="value">
              {source.duration_ms ? `${(source.duration_ms / 1000).toFixed(1)}s` : "—"}
            </span>
          </div>
          <div className="meta-item">
            <span className="label">Regulatory Body</span>
            <span className="value">{source.regulatory_body}</span>
          </div>
          <div className="meta-item">
            <span className="label">Status</span>
            <span className={`badge badge-success`}>{source.status}</span>
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
