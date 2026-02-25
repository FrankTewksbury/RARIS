import type { AcquisitionSourceStatus } from "../types/acquisition";

interface Props {
  sources: AcquisitionSourceStatus[];
  onRetry: (sourceId: string) => void;
  onRetryAll: () => void;
}

export function ErrorLogPanel({ sources, onRetry, onRetryAll }: Props) {
  const failedSources = sources.filter((s) => s.status === "failed");

  if (failedSources.length === 0) return null;

  return (
    <div className="panel error-log-panel">
      <h2>
        Failed Sources ({failedSources.length})
        <button className="btn-sm" style={{ marginLeft: "0.75rem" }} onClick={onRetryAll}>
          Retry All
        </button>
      </h2>

      <ul className="error-list">
        {failedSources.map((source) => (
          <li key={source.source_id}>
            <div className="error-item">
              <strong>{source.name}</strong>
              <span className="error-detail">{source.error}</span>
              <span className="error-meta">
                Retries: {source.retry_count}
              </span>
              <button className="btn-sm" onClick={() => onRetry(source.source_id)}>
                Retry
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
