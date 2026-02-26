import { useVertical } from "../../hooks/useVerticals";
import {
  useTriggerDiscovery,
  useTriggerAcquisition,
  useTriggerIngestion,
} from "../../hooks/useVerticals";
import { PHASE_COLORS } from "../../types/vertical";

interface Props {
  verticalId: string;
}

const PHASE_STEPS = ["discovery", "acquisition", "ingestion", "indexed"] as const;
const PHASE_STEP_LABELS: Record<string, string> = {
  discovery: "Discovery",
  acquisition: "Acquisition",
  ingestion: "Ingestion",
  indexed: "Indexed",
};

export function PipelineTracker({ verticalId }: Props) {
  const { data: vertical } = useVertical(verticalId);
  const triggerDiscovery = useTriggerDiscovery();
  const triggerAcquisition = useTriggerAcquisition();
  const triggerIngestion = useTriggerIngestion();

  if (!vertical) return null;

  const pipelineMap = new Map(
    vertical.pipeline_status.map((p) => [p.phase, p])
  );

  const canTrigger = (phase: string): boolean => {
    if (phase === "discovery") return vertical.phase === "created" || vertical.phase === "failed";
    if (phase === "acquisition") return vertical.phase === "discovered" || vertical.phase === "failed";
    if (phase === "ingestion") return vertical.phase === "acquired" || vertical.phase === "failed";
    return false;
  };

  const handleTrigger = (phase: string) => {
    if (phase === "discovery") triggerDiscovery.mutate(verticalId);
    if (phase === "acquisition") triggerAcquisition.mutate(verticalId);
    if (phase === "ingestion") triggerIngestion.mutate(verticalId);
  };

  const isTriggering =
    triggerDiscovery.isPending ||
    triggerAcquisition.isPending ||
    triggerIngestion.isPending;

  return (
    <div className="panel">
      <h3>{vertical.name}</h3>
      <p className="text-muted" style={{ marginBottom: "1rem" }}>
        {vertical.domain_description.slice(0, 200)}
        {vertical.domain_description.length > 200 ? "..." : ""}
      </p>

      {/* Pipeline phases */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        {PHASE_STEPS.map((phase, i) => {
          const status = pipelineMap.get(phase);
          const statusVal = status?.status || "pending";
          const color = PHASE_COLORS[statusVal] || "var(--text-muted)";

          return (
            <div key={phase} style={{ flex: 1, textAlign: "center" }}>
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                gap: "0.25rem", marginBottom: "0.25rem",
              }}>
                {i > 0 && (
                  <div style={{
                    flex: 1, height: "2px",
                    background: statusVal === "complete" ? "var(--success)" : "var(--border)",
                  }} />
                )}
                <div style={{
                  width: "24px", height: "24px", borderRadius: "50%",
                  background: color, display: "flex", alignItems: "center",
                  justifyContent: "center", color: "white", fontSize: "0.7rem",
                  fontWeight: 700,
                }}>
                  {statusVal === "complete" ? "\u2713" : statusVal === "running" ? "\u25CF" : i + 1}
                </div>
                {i < PHASE_STEPS.length - 1 && (
                  <div style={{
                    flex: 1, height: "2px",
                    background: statusVal === "complete" ? "var(--success)" : "var(--border)",
                  }} />
                )}
              </div>
              <div style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                {PHASE_STEP_LABELS[phase]}
              </div>
              <div style={{ fontSize: "0.7rem", color }}>
                {statusVal}
              </div>
              {canTrigger(phase) && phase !== "indexed" && (
                <button
                  onClick={() => handleTrigger(phase)}
                  disabled={isTriggering}
                  style={{ fontSize: "0.75rem", marginTop: "0.25rem", padding: "0.2rem 0.5rem" }}
                >
                  Start
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "0.75rem" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--primary)" }}>
            {vertical.source_count}
          </div>
          <div className="text-muted">Sources</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--success)" }}>
            {vertical.document_count}
          </div>
          <div className="text-muted">Documents</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--warning)" }}>
            {vertical.chunk_count}
          </div>
          <div className="text-muted">Chunks</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: vertical.coverage_score >= vertical.coverage_target ? "var(--success)" : "var(--warning)" }}>
            {(vertical.coverage_score * 100).toFixed(0)}%
          </div>
          <div className="text-muted">Coverage</div>
        </div>
      </div>

      {/* Error display */}
      {vertical.last_error && (
        <div style={{ marginTop: "1rem", padding: "0.75rem", background: "var(--bg-danger, rgba(239,68,68,0.1))", borderRadius: "4px" }}>
          <strong>Error:</strong> {vertical.last_error}
        </div>
      )}

      {/* Resource links */}
      <div style={{ marginTop: "1rem", display: "flex", gap: "1rem", fontSize: "0.85rem" }}>
        {vertical.manifest_id && (
          <span className="text-muted">Manifest: <code>{vertical.manifest_id}</code></span>
        )}
        {vertical.acquisition_id && (
          <span className="text-muted">Acquisition: <code>{vertical.acquisition_id}</code></span>
        )}
        {vertical.ingestion_id && (
          <span className="text-muted">Ingestion: <code>{vertical.ingestion_id}</code></span>
        )}
      </div>
    </div>
  );
}
