import { useState } from "react";
import { DomainInputPanel } from "../components/DomainInputPanel";
import { AgentProgressPanel } from "../components/AgentProgressPanel";
import { ManifestSummaryCard } from "../components/ManifestSummaryCard";
import { SourcesTable } from "../components/SourcesTable";
import { CoverageSummary } from "../components/CoverageSummary";
import { ManifestActions } from "../components/ManifestActions";
import { useManifest, useManifestList, useUpdateSource, useApproveManifest, useRejectManifest } from "../hooks/useManifests";
import { useSSE } from "../hooks/useSSE";
import type { Source } from "../types/manifest";

export function Dashboard() {
  const [activeManifestId, setActiveManifestId] = useState<string | undefined>();
  const { events, isConnected, connect } = useSSE();

  const { data: manifests } = useManifestList();
  const { data: manifest, refetch } = useManifest(activeManifestId);
  const updateSource = useUpdateSource(activeManifestId || "");
  const approveManifest = useApproveManifest();
  const rejectManifest = useRejectManifest();

  const handleGenerate = (manifestId: string, streamUrl: string) => {
    setActiveManifestId(manifestId);
    connect(streamUrl);
  };

  const handleUpdateSource = (sourceId: string, update: Partial<Source>) => {
    if (!activeManifestId) return;
    updateSource.mutate({ sourceId, update });
  };

  // When SSE completes, refetch manifest data
  const isComplete = events.some((e) => e.step === "complete");
  if (isComplete && activeManifestId && !manifest) {
    refetch();
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>RARIS — Domain Discovery</h1>
      </header>

      <div className="dashboard-content">
        <DomainInputPanel onGenerate={handleGenerate} isGenerating={isConnected} />

        <AgentProgressPanel events={events} isConnected={isConnected} />

        {/* Manifest list sidebar */}
        {manifests && manifests.length > 0 && (
          <div className="panel manifest-list-panel">
            <h2>Manifests</h2>
            <ul>
              {manifests.map((m) => (
                <li
                  key={m.id}
                  className={m.id === activeManifestId ? "active" : ""}
                  onClick={() => setActiveManifestId(m.id)}
                >
                  <strong>{m.domain}</strong>
                  <span className={`badge badge-${m.status === "approved" ? "success" : "warning"}`}>
                    {m.status}
                  </span>
                  <span>{m.sources_count} sources</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {manifest && (
          <>
            <ManifestSummaryCard manifest={manifest} />
            <SourcesTable sources={manifest.sources} onUpdateSource={handleUpdateSource} />
            {manifest.coverage_assessment && (
              <CoverageSummary coverage={manifest.coverage_assessment} />
            )}
            <ManifestActions
              manifest={manifest}
              onApprove={(review) =>
                approveManifest.mutate({ id: manifest.id, review })
              }
              onReject={(review) =>
                rejectManifest.mutate({ id: manifest.id, review })
              }
            />
          </>
        )}
      </div>
    </div>
  );
}
