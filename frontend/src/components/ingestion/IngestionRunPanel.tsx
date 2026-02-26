import { useState } from "react";
import type { AcquisitionRunSummary } from "../../types/acquisition";
import { useStartIngestion, useIngestionRun } from "../../hooks/useIngestion";
import { useAcquisitionList } from "../../hooks/useAcquisitions";

interface Props {
  onRunStarted: (ingestionId: string) => void;
  activeRunId: string | undefined;
}

export function IngestionRunPanel({ onRunStarted, activeRunId }: Props) {
  const [selectedAcqId, setSelectedAcqId] = useState("");
  const { data: acquisitions } = useAcquisitionList();
  const { data: activeRun } = useIngestionRun(activeRunId);
  const startMutation = useStartIngestion();

  const completedAcqs = (acquisitions ?? []).filter(
    (a: AcquisitionRunSummary) => a.status === "complete"
  );

  const handleStart = async () => {
    if (!selectedAcqId) return;
    const result = await startMutation.mutateAsync(selectedAcqId);
    onRunStarted(result.ingestion_id);
  };

  const progress = activeRun
    ? Math.round(
        ((activeRun.processed + activeRun.failed) / Math.max(activeRun.total_documents, 1)) * 100
      )
    : 0;

  return (
    <div className="panel">
      <h3>Ingestion Run</h3>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <select
          value={selectedAcqId}
          onChange={(e) => setSelectedAcqId(e.target.value)}
          style={{ flex: 1 }}
        >
          <option value="">Select acquisition run...</option>
          {completedAcqs.map((a: AcquisitionRunSummary) => (
            <option key={a.acquisition_id} value={a.acquisition_id}>
              {a.acquisition_id} — {a.completed} sources ({a.manifest_id})
            </option>
          ))}
        </select>
        <button
          onClick={handleStart}
          disabled={!selectedAcqId || startMutation.isPending}
        >
          {startMutation.isPending ? "Starting..." : "Start Ingestion"}
        </button>
      </div>

      {activeRun && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
            <span className="text-muted">
              {activeRun.status === "complete" ? "Complete" : `Processing... ${progress}%`}
            </span>
            <span className="text-muted">
              {activeRun.processed + activeRun.failed} / {activeRun.total_documents}
            </span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div style={{ display: "flex", gap: "1rem", marginTop: "0.5rem" }}>
            <span className="badge badge-success">{activeRun.processed} processed</span>
            {activeRun.failed > 0 && (
              <span className="badge badge-danger">{activeRun.failed} failed</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
