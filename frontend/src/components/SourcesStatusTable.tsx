import { useState } from "react";
import type { AcquisitionSourceStatus, SourceAcqStatus } from "../types/acquisition";

interface Props {
  sources: AcquisitionSourceStatus[];
  onRetry: (sourceId: string) => void;
  onViewSource: (sourceId: string) => void;
}

const PAGE_SIZE = 25;

const STATUS_COLORS: Record<string, string> = {
  pending: "badge-neutral",
  running: "badge-active",
  complete: "badge-success",
  failed: "badge-danger",
  retrying: "badge-warning",
  skipped: "badge-neutral",
};

export function SourcesStatusTable({ sources, onRetry, onViewSource }: Props) {
  const [filterStatus, setFilterStatus] = useState<SourceAcqStatus | "">("");
  const [filterMethod, setFilterMethod] = useState("");
  const [page, setPage] = useState(0);

  let filtered = [...sources];
  if (filterStatus) filtered = filtered.filter((s) => s.status === filterStatus);
  if (filterMethod) filtered = filtered.filter((s) => s.access_method === filterMethod);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div className="panel sources-status-panel">
      <h2>Sources ({filtered.length})</h2>

      <div className="filters">
        <select
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value as SourceAcqStatus | ""); setPage(0); }}
        >
          <option value="">All Statuses</option>
          {["pending", "running", "complete", "failed", "retrying", "skipped"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          value={filterMethod}
          onChange={(e) => { setFilterMethod(e.target.value); setPage(0); }}
        >
          <option value="">All Methods</option>
          {["scrape", "download", "api", "manual"].map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Body</th>
            <th>Method</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Error</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {paged.map((source) => (
            <tr key={source.source_id}>
              <td>{source.name}</td>
              <td>{source.regulatory_body}</td>
              <td>{source.access_method}</td>
              <td>
                <span className={`badge ${STATUS_COLORS[source.status] || "badge-neutral"}`}>
                  {source.status}
                </span>
              </td>
              <td>{source.duration_ms ? `${(source.duration_ms / 1000).toFixed(1)}s` : "—"}</td>
              <td className="error-cell">{source.error || "—"}</td>
              <td>
                {source.status === "complete" && (
                  <button className="btn-sm" onClick={() => onViewSource(source.source_id)}>
                    View
                  </button>
                )}
                {source.status === "failed" && (
                  <button className="btn-sm" onClick={() => onRetry(source.source_id)}>
                    Retry
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page === 0} onClick={() => setPage(page - 1)}>Prev</button>
          <span>Page {page + 1} of {totalPages}</span>
          <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}
