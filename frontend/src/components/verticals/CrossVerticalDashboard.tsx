import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { useVerticalList } from "../../hooks/useVerticals";

const COLORS = ["#3b82f6", "#22c55e", "#eab308", "#ef4444", "#8b5cf6", "#ec4899"];

export function CrossVerticalDashboard() {
  const { data: verticals } = useVerticalList();

  if (!verticals || verticals.length === 0) {
    return (
      <div className="panel">
        <h3>Cross-Vertical Overview</h3>
        <p className="text-muted">No verticals to compare.</p>
      </div>
    );
  }

  const chartData = verticals.map((v) => ({
    name: v.name.length > 20 ? v.name.slice(0, 20) + "..." : v.name,
    sources: v.source_count,
    documents: v.document_count,
    chunks: v.chunk_count,
    coverage: Math.round(v.coverage_score * 100),
  }));

  const totalSources = verticals.reduce((s, v) => s + v.source_count, 0);
  const totalDocs = verticals.reduce((s, v) => s + v.document_count, 0);
  const totalChunks = verticals.reduce((s, v) => s + v.chunk_count, 0);
  const indexedCount = verticals.filter((v) => v.phase === "indexed").length;

  return (
    <div className="panel">
      <h3>Cross-Vertical Overview</h3>

      {/* Summary stats */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "var(--primary)" }}>
            {verticals.length}
          </div>
          <div className="text-muted">Verticals</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "var(--success)" }}>
            {indexedCount}
          </div>
          <div className="text-muted">Indexed</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 700 }}>
            {totalSources}
          </div>
          <div className="text-muted">Total Sources</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 700 }}>
            {totalDocs} / {totalChunks}
          </div>
          <div className="text-muted">Docs / Chunks</div>
        </div>
      </div>

      {/* Source comparison chart */}
      {chartData.length > 1 && (
        <div style={{ marginBottom: "1rem" }}>
          <h4 style={{ marginBottom: "0.5rem" }}>Sources by Vertical</h4>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData}>
              <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
              <YAxis tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="sources">
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Coverage comparison chart */}
      {chartData.length > 1 && (
        <div>
          <h4 style={{ marginBottom: "0.5rem" }}>Coverage Score (%)</h4>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData}>
              <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="coverage">
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
