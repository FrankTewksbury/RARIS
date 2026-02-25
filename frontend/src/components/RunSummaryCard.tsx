import type { AcquisitionRunDetail } from "../types/acquisition";

interface Props {
  run: AcquisitionRunDetail;
}

function formatElapsed(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

export function RunSummaryCard({ run }: Props) {
  const progressPct = run.total_sources > 0
    ? ((run.completed / run.total_sources) * 100).toFixed(0)
    : "0";

  return (
    <div className="panel run-summary-card">
      <h2>Acquisition Run</h2>
      <div className="summary-grid">
        <div className="summary-item">
          <span className="label">Manifest</span>
          <span className="value">{run.manifest_id}</span>
        </div>
        <div className="summary-item">
          <span className="label">Status</span>
          <span className={`badge badge-${run.status === "complete" ? "success" : run.status === "running" ? "active" : "warning"}`}>
            {run.status}
          </span>
        </div>
        <div className="summary-item">
          <span className="label">Progress</span>
          <span className="value">{progressPct}%</span>
        </div>
        <div className="summary-item">
          <span className="label">Elapsed</span>
          <span className="value">{formatElapsed(run.elapsed_seconds)}</span>
        </div>
      </div>

      <div className="progress-bar-container">
        <div className="progress-bar" style={{ width: `${progressPct}%` }} />
      </div>

      <div className="run-counts">
        <span className="count-item count-complete">{run.completed} complete</span>
        <span className="count-item count-failed">{run.failed} failed</span>
        <span className="count-item count-pending">{run.pending} pending</span>
        <span className="count-item count-retrying">{run.retrying} retrying</span>
      </div>
    </div>
  );
}
