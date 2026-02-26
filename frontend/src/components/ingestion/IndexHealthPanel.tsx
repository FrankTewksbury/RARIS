import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { useIndexStats } from "../../hooks/useIngestion";

const COLORS = ["#3b82f6", "#22c55e", "#eab308", "#ef4444", "#8b5cf6", "#ec4899"];

export function IndexHealthPanel() {
  const { data: stats } = useIndexStats();

  if (!stats) {
    return (
      <div className="panel">
        <h3>Index Health</h3>
        <p className="text-muted">No index data yet.</p>
      </div>
    );
  }

  const jurisdictionData = Object.entries(stats.by_jurisdiction).map(([name, count]) => ({
    name,
    count,
  }));

  const typeData = Object.entries(stats.by_document_type).map(([name, count]) => ({
    name,
    count,
  }));

  const embeddingCoverage = stats.total_chunks > 0
    ? Math.round((stats.indexed_chunks / stats.total_chunks) * 100)
    : 0;

  return (
    <div className="panel">
      <h3>Index Health</h3>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "var(--primary)" }}>
            {stats.total_documents}
          </div>
          <div className="text-muted">Documents</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "var(--success)" }}>
            {stats.indexed_documents}
          </div>
          <div className="text-muted">Indexed</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "var(--warning)" }}>
            {stats.total_chunks}
          </div>
          <div className="text-muted">Chunks</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 700, color: embeddingCoverage === 100 ? "var(--success)" : "var(--warning)" }}>
            {embeddingCoverage}%
          </div>
          <div className="text-muted">Embedded</div>
        </div>
      </div>

      {jurisdictionData.length > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          <h4 style={{ marginBottom: "0.5rem" }}>By Jurisdiction</h4>
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={jurisdictionData}>
              <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
              <YAxis tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count">
                {jurisdictionData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {typeData.length > 0 && (
        <div>
          <h4 style={{ marginBottom: "0.5rem" }}>By Document Type</h4>
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={typeData}>
              <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
              <YAxis tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count">
                {typeData.map((_, i) => (
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
