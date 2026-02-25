import type { ManifestDetail } from "../types/manifest";

interface Props {
  manifest: ManifestDetail;
}

function statusColor(status: string): string {
  switch (status) {
    case "approved": return "badge-success";
    case "pending_review": return "badge-warning";
    case "generating": return "badge-active";
    default: return "badge-neutral";
  }
}

function coverageColor(score: number): string {
  if (score >= 0.85) return "score-green";
  if (score >= 0.70) return "score-yellow";
  return "score-red";
}

export function ManifestSummaryCard({ manifest }: Props) {
  return (
    <div className="panel manifest-summary-card">
      <h2>Manifest Summary</h2>
      <div className="summary-grid">
        <div className="summary-item">
          <span className="label">Domain</span>
          <span className="value">{manifest.domain}</span>
        </div>
        <div className="summary-item">
          <span className="label">Sources</span>
          <span className="value">{manifest.sources_count}</span>
        </div>
        <div className="summary-item">
          <span className="label">Coverage</span>
          <span className={`value ${coverageColor(manifest.coverage_score)}`}>
            {(manifest.coverage_score * 100).toFixed(0)}%
          </span>
        </div>
        <div className="summary-item">
          <span className="label">Status</span>
          <span className={`badge ${statusColor(manifest.status)}`}>
            {manifest.status}
          </span>
        </div>
        <div className="summary-item">
          <span className="label">Created</span>
          <span className="value">{new Date(manifest.created).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  );
}
