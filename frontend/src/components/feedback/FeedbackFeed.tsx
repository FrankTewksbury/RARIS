import { useState } from "react";
import { useFeedbackList, useResolveFeedback } from "../../hooks/useFeedback";
import { FEEDBACK_TYPES, STATUS_COLORS } from "../../types/feedback";

export function FeedbackFeed() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const { data: feedback, isLoading } = useFeedbackList(
    statusFilter || undefined,
    typeFilter || undefined,
  );
  const resolve = useResolveFeedback();
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolution, setResolution] = useState("");

  const handleResolve = (id: string, status: string) => {
    resolve.mutate(
      { id, request: { resolution: resolution || `Marked as ${status}`, status } },
      { onSuccess: () => { setResolvingId(null); setResolution(""); } },
    );
  };

  return (
    <div className="panel">
      <h3>Feedback Feed</h3>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="investigating">Investigating</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">All Types</option>
          {FEEDBACK_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-muted">Loading...</p>}

      {feedback && feedback.length === 0 && (
        <p className="text-muted">No feedback submitted yet.</p>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {feedback?.map((fb) => {
          const typeInfo = FEEDBACK_TYPES.find((t) => t.value === fb.feedback_type);
          return (
            <div
              key={fb.id}
              style={{
                padding: "0.75rem",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                borderLeft: `4px solid ${typeInfo?.color || "var(--border)"}`,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <span style={{
                    fontSize: "0.75rem", fontWeight: 600,
                    padding: "0.15rem 0.4rem", borderRadius: "4px",
                    background: typeInfo?.color || "var(--border)", color: "white",
                  }}>
                    {typeInfo?.label || fb.feedback_type}
                  </span>
                  <span style={{
                    fontSize: "0.75rem", fontWeight: 500,
                    color: STATUS_COLORS[fb.status] || "var(--text-muted)",
                  }}>
                    {fb.status}
                  </span>
                  <code style={{ fontSize: "0.7rem" }}>{fb.id}</code>
                </div>
                <span className="text-muted" style={{ fontSize: "0.75rem" }}>
                  {new Date(fb.submitted_at).toLocaleDateString()}
                </span>
              </div>

              {fb.description && (
                <p style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>{fb.description}</p>
              )}

              {fb.auto_action && (
                <div style={{ fontSize: "0.75rem", color: "var(--primary)", marginTop: "0.25rem" }}>
                  Auto-action: {fb.auto_action}
                </div>
              )}

              {fb.traced_source_id && (
                <div style={{ fontSize: "0.75rem", marginTop: "0.25rem" }} className="text-muted">
                  Traced to source: <code>{fb.traced_source_id}</code>
                </div>
              )}

              {fb.status === "pending" && (
                <div style={{ marginTop: "0.5rem" }}>
                  {resolvingId === fb.id ? (
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <input
                        type="text"
                        placeholder="Resolution note..."
                        value={resolution}
                        onChange={(e) => setResolution(e.target.value)}
                        style={{ flex: 1, padding: "0.3rem 0.5rem", fontSize: "0.8rem" }}
                      />
                      <button
                        onClick={() => handleResolve(fb.id, "resolved")}
                        disabled={resolve.isPending}
                        style={{ fontSize: "0.75rem", padding: "0.3rem 0.5rem" }}
                      >
                        Resolve
                      </button>
                      <button
                        onClick={() => handleResolve(fb.id, "dismissed")}
                        disabled={resolve.isPending}
                        style={{ fontSize: "0.75rem", padding: "0.3rem 0.5rem" }}
                      >
                        Dismiss
                      </button>
                      <button
                        onClick={() => setResolvingId(null)}
                        style={{ fontSize: "0.75rem", padding: "0.3rem 0.5rem" }}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setResolvingId(fb.id)}
                      style={{ fontSize: "0.75rem", padding: "0.3rem 0.5rem" }}
                    >
                      Review
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
