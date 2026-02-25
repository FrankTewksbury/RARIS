import { useState } from "react";
import type { ManifestSummary } from "../types/manifest";
import type { AcquisitionRunSummary } from "../types/acquisition";

interface Props {
  manifests: ManifestSummary[];
  acquisitions: AcquisitionRunSummary[];
  onStart: (manifestId: string) => void;
  onSelectRun: (acquisitionId: string) => void;
  isStarting: boolean;
}

export function RunSelector({ manifests, acquisitions, onStart, onSelectRun, isStarting }: Props) {
  const [selectedManifest, setSelectedManifest] = useState("");

  const approvedManifests = manifests.filter((m) => m.status === "approved");

  return (
    <div className="panel run-selector-panel">
      <h2>Acquisition Runs</h2>

      <div className="form-row">
        <label>
          Manifest:
          <select
            value={selectedManifest}
            onChange={(e) => setSelectedManifest(e.target.value)}
            disabled={isStarting}
          >
            <option value="">Select approved manifest...</option>
            {approvedManifests.map((m) => (
              <option key={m.id} value={m.id}>
                {m.domain} ({m.sources_count} sources)
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={() => {
            if (selectedManifest) onStart(selectedManifest);
          }}
          disabled={!selectedManifest || isStarting}
        >
          {isStarting ? "Starting..." : "Start Acquisition"}
        </button>
      </div>

      {acquisitions.length > 0 && (
        <ul className="run-list">
          {acquisitions.map((run) => (
            <li key={run.acquisition_id} onClick={() => onSelectRun(run.acquisition_id)}>
              <span className={`badge badge-${run.status === "complete" ? "success" : run.status === "running" ? "active" : "warning"}`}>
                {run.status}
              </span>
              <span>{run.manifest_id}</span>
              <span className="run-stats">
                {run.completed}/{run.total_sources} complete
                {run.failed > 0 && <span className="score-red"> | {run.failed} failed</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
