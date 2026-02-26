import { useVerticalList } from "../../hooks/useVerticals";
import { PHASE_LABELS } from "../../types/vertical";

interface Props {
  activeId: string | undefined;
  onSelect: (id: string) => void;
}

export function VerticalRegistry({ activeId, onSelect }: Props) {
  const { data: verticals } = useVerticalList();

  const phaseClass = (phase: string) => {
    if (phase === "indexed") return "badge-success";
    if (phase === "failed") return "badge-danger";
    if (phase.endsWith("ing")) return "badge-warning";
    return "";
  };

  return (
    <div className="panel">
      <h3>Verticals</h3>

      {!verticals || verticals.length === 0 ? (
        <p className="text-muted">No verticals configured yet.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Name</th>
              <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Phase</th>
              <th style={{ textAlign: "right", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Sources</th>
              <th style={{ textAlign: "right", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Docs</th>
              <th style={{ textAlign: "right", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Chunks</th>
              <th style={{ textAlign: "right", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Coverage</th>
            </tr>
          </thead>
          <tbody>
            {verticals.map((v) => (
              <tr
                key={v.id}
                onClick={() => onSelect(v.id)}
                style={{
                  cursor: "pointer",
                  background: v.id === activeId ? "var(--bg-hover, rgba(59,130,246,0.1))" : undefined,
                }}
              >
                <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)", fontWeight: 600 }}>
                  {v.name}
                </td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>
                  <span className={`badge ${phaseClass(v.phase)}`}>
                    {PHASE_LABELS[v.phase] || v.phase}
                  </span>
                </td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)", textAlign: "right" }}>
                  {v.source_count}
                </td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)", textAlign: "right" }}>
                  {v.document_count}
                </td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)", textAlign: "right" }}>
                  {v.chunk_count}
                </td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)", textAlign: "right" }}>
                  {(v.coverage_score * 100).toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
