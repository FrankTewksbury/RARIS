import { useState } from "react";
import { useCurationQueue, useProcessQueueItem } from "../../hooks/useFeedback";
import { PRIORITY_COLORS, STATUS_COLORS } from "../../types/feedback";

export function ReCurationQueue() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data: items, isLoading } = useCurationQueue(statusFilter || undefined);
  const processItem = useProcessQueueItem();

  return (
    <div className="panel">
      <h3>Re-Curation Queue</h3>

      <div style={{ marginBottom: "1rem" }}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="processing">Processing</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>
      </div>

      {isLoading && <p className="text-muted">Loading...</p>}

      {items && items.length === 0 && (
        <p className="text-muted">No items in the re-curation queue.</p>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {items?.map((item) => (
          <div
            key={item.id}
            style={{
              padding: "0.75rem",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              borderLeft: `4px solid ${PRIORITY_COLORS[item.priority] || "var(--border)"}`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <span style={{
                  fontSize: "0.7rem", fontWeight: 600, textTransform: "uppercase",
                  padding: "0.1rem 0.3rem", borderRadius: "3px",
                  background: PRIORITY_COLORS[item.priority] || "var(--border)", color: "white",
                }}>
                  {item.priority}
                </span>
                <span style={{
                  fontSize: "0.75rem", fontWeight: 500,
                  color: STATUS_COLORS[item.status] || "var(--text-muted)",
                }}>
                  {item.status}
                </span>
                <span className="text-muted" style={{ fontSize: "0.7rem" }}>
                  {item.trigger_type}
                </span>
              </div>
              <span className="text-muted" style={{ fontSize: "0.75rem" }}>
                {new Date(item.created_at).toLocaleDateString()}
              </span>
            </div>

            <p style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>{item.reason}</p>

            <div style={{ fontSize: "0.75rem", marginTop: "0.25rem" }} className="text-muted">
              Source: <code>{item.source_id}</code> | Manifest: <code>{item.manifest_id}</code>
            </div>

            {item.status === "pending" && (
              <button
                onClick={() => processItem.mutate(item.id)}
                disabled={processItem.isPending}
                style={{ fontSize: "0.75rem", padding: "0.3rem 0.5rem", marginTop: "0.5rem" }}
              >
                Process
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
