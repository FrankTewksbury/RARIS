import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useAccuracyDashboard } from "../../hooks/useFeedback";
import { FEEDBACK_TYPES } from "../../types/feedback";

export function CorpusHealth() {
  const { data: dashboard, isLoading } = useAccuracyDashboard();

  if (isLoading) return <div className="panel"><p className="text-muted">Loading...</p></div>;
  if (!dashboard) return null;

  const { current, by_feedback_type, by_vertical } = dashboard;

  const feedbackChartData = FEEDBACK_TYPES.map((t) => ({
    name: t.label,
    count: by_feedback_type[t.value] || 0,
    color: t.color,
  }));

  const verticalData = Object.entries(by_vertical).map(([name, score]) => ({
    name: name.length > 18 ? name.slice(0, 18) + "..." : name,
    coverage: Math.round(score * 100),
  }));

  const accuracyPct = Math.round(current.accuracy_score * 100);
  const resolutionPct = Math.round(current.resolution_rate * 100);
  const confidencePct = Math.round(current.avg_source_confidence * 100);

  return (
    <div className="panel">
      <h3>Corpus Health</h3>

      {/* Key metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            fontSize: "2rem", fontWeight: 700,
            color: accuracyPct >= 80 ? "var(--success)" : accuracyPct >= 60 ? "var(--warning)" : "var(--danger, #ef4444)",
          }}>
            {accuracyPct}%
          </div>
          <div className="text-muted">Accuracy</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2rem", fontWeight: 700, color: "var(--primary)" }}>
            {resolutionPct}%
          </div>
          <div className="text-muted">Resolution Rate</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2rem", fontWeight: 700, color: "var(--success)" }}>
            {confidencePct}%
          </div>
          <div className="text-muted">Avg Confidence</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2rem", fontWeight: 700 }}>
            {current.total_feedback}
          </div>
          <div className="text-muted">Total Feedback</div>
        </div>
      </div>

      {/* Secondary metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
        <div style={{ textAlign: "center", padding: "0.5rem", border: "1px solid var(--border)", borderRadius: "6px" }}>
          <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--warning)" }}>
            {current.pending_queue_items}
          </div>
          <div className="text-muted" style={{ fontSize: "0.8rem" }}>Pending Queue</div>
        </div>
        <div style={{ textAlign: "center", padding: "0.5rem", border: "1px solid var(--border)", borderRadius: "6px" }}>
          <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--danger, #ef4444)" }}>
            {current.unresolved_changes}
          </div>
          <div className="text-muted" style={{ fontSize: "0.8rem" }}>Unresolved Changes</div>
        </div>
        <div style={{ textAlign: "center", padding: "0.5rem", border: "1px solid var(--border)", borderRadius: "6px" }}>
          <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--text-muted)" }}>
            {current.stale_sources}
          </div>
          <div className="text-muted" style={{ fontSize: "0.8rem" }}>Stale Sources</div>
        </div>
      </div>

      {/* Feedback by type chart */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h4 style={{ marginBottom: "0.5rem", fontSize: "0.9rem" }}>Feedback by Type</h4>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={feedbackChartData}>
            <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
            <YAxis tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="count">
              {feedbackChartData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Coverage by vertical */}
      {verticalData.length > 0 && (
        <div>
          <h4 style={{ marginBottom: "0.5rem", fontSize: "0.9rem" }}>Coverage by Vertical (%)</h4>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={verticalData}>
              <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="coverage" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
