import { useState } from "react";
import { RunSelector } from "../components/RunSelector";
import { RunSummaryCard } from "../components/RunSummaryCard";
import { SourcesStatusTable } from "../components/SourcesStatusTable";
import { ErrorLogPanel } from "../components/ErrorLogPanel";
import { RawContentViewer } from "../components/RawContentViewer";
import { useManifestList } from "../hooks/useManifests";
import {
  useAcquisition,
  useAcquisitionList,
  useAcquisitionSources,
  useRetrySource,
  useStartAcquisition,
} from "../hooks/useAcquisitions";

export function AcquisitionMonitor() {
  const [activeRunId, setActiveRunId] = useState<string | undefined>();
  const [viewingSourceId, setViewingSourceId] = useState<string | null>(null);

  const { data: manifests } = useManifestList();
  const { data: acquisitions } = useAcquisitionList();
  const { data: run } = useAcquisition(activeRunId);
  const { data: sources } = useAcquisitionSources(activeRunId);
  const startAcquisition = useStartAcquisition();
  const retrySource = useRetrySource(activeRunId || "");

  const handleStart = (manifestId: string) => {
    startAcquisition.mutate(manifestId, {
      onSuccess: (data) => setActiveRunId(data.acquisition_id),
    });
  };

  const handleRetry = (sourceId: string) => {
    retrySource.mutate(sourceId);
  };

  const handleRetryAll = () => {
    if (!sources) return;
    for (const source of sources.filter((s) => s.status === "failed")) {
      retrySource.mutate(source.source_id);
    }
  };

  const viewingSource = sources?.find((s) => s.source_id === viewingSourceId);

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>RARIS — Acquisition Monitor</h1>
      </header>

      <div className="dashboard-content">
        <RunSelector
          manifests={manifests || []}
          acquisitions={acquisitions || []}
          onStart={handleStart}
          onSelectRun={setActiveRunId}
          isStarting={startAcquisition.isPending}
        />

        {run && <RunSummaryCard run={run} />}

        {sources && (
          <SourcesStatusTable
            sources={sources}
            onRetry={handleRetry}
            onViewSource={setViewingSourceId}
          />
        )}

        {sources && (
          <ErrorLogPanel
            sources={sources}
            onRetry={handleRetry}
            onRetryAll={handleRetryAll}
          />
        )}

        {viewingSource && (
          <RawContentViewer
            source={viewingSource}
            onClose={() => setViewingSourceId(null)}
          />
        )}
      </div>
    </div>
  );
}
