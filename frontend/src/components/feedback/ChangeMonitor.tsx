import { useState } from "react";
import { useChangeList, useTriggerMonitor } from "../../hooks/useFeedback";
import { STATUS_COLORS } from "../../types/feedback";

export function ChangeMonitor() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data: changes, isLoading } = useChangeList(statusFilter || undefined);
  const triggerMonitor = useTriggerMonitor();

  return (
    <div className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h3 style={{ margin: 0 }}>Change Monitor</h3>
        <button
          onClick={() => triggerMonitor.mutate()}
          disabled={triggerMonitor.isPending}
        >
          {triggerMonitor.isPending ? "Running..." : "Run Monitor"}
        </button>
      </div>

      {triggerMonitor.isSuccess && triggerMonitor.data && (
        <div style={{
          padding: "0.5rem 0.75rem", marginBottom: "1rem",
          background: "var(--bg-success, rgba(34,197,94,0.1))", borderRadius: "4px",
          fontSize: "0.85rem",
        }}>
          {triggerMonitor.data.message}
        </div>
      )}

      <div style={{ marginBottom: "1rem" }}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="detected">Detected</option>
          <option value="processing">Processing</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>
      </div>

      {isLoading && <p className="text-muted">Loading...</p>}

      {changes && changes.length === 0 && (
        <p className="text-muted">No regulatory changes detected.</p>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {changes?.map((evt) => (
          <div
            key={evt.id}
            style={{
              padding: "0.75rem",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              borderLeft: `4px solid ${STATUS_COLORS[evt.status] || "var(--border)"}`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <span style={{
                  fontSize: "0.7rem", fontWeight: 600, textTransform: "uppercase",
                  padding: "0.1rem 0.3rem", borderRadius: "3px",
                  background: "var(--primary)", color: "white",
                }}>
                  {evt.change_type.replace("_", " ")}
                </span>
                <span style={{
                  fontSize: "0.75rem", fontWeight: 500,
                  color: STATUS_COLORS[evt.status] || "var(--text-muted)",
                }}>
                  {evt.status}
                </span>
                <span className="text-muted" style={{ fontSize: "0.7rem" }}>
                  via {evt.detection_method}
                </span>
              </div>
              <span className="text-muted" style={{ fontSize: "0.75rem" }}>
                {new Date(evt.detected_at).toLocaleDateString()}
              </span>
            </div>

            <p style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>{evt.description}</p>

            <div style={{ fontSize: "0.75rem", marginTop: "0.25rem" }} className="text-muted">
              Source: <code>{evt.source_id}</code> | Manifest: <code>{evt.manifest_id}</code>
            </div>

            {evt.impact_assessment && (
              <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", fontStyle: "italic" }}>
                Impact: {evt.impact_assessment}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
