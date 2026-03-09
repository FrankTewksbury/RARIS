import { useEffect, useState } from "react";
import { DomainInputPanel } from "../components/DomainInputPanel";
import { AgentProgressPanel } from "../components/AgentProgressPanel";
import { ManifestSummaryCard } from "../components/ManifestSummaryCard";
import { ProgramsTable } from "../components/ProgramsTable";
import { SourcesTable } from "../components/SourcesTable";
import { CoverageSummary } from "../components/CoverageSummary";
import { ManifestActions } from "../components/ManifestActions";
import { useManifest, useManifestList, useUpdateSource, useApproveManifest, useRejectManifest } from "../hooks/useManifests";
import { useSSE } from "../hooks/useSSE";
import type { Source } from "../types/manifest";

export function Dashboard() {
  const [activeManifestId, setActiveManifestId] = useState<string | undefined>();
  const [showResults, setShowResults] = useState(false);
  const { events, isConnected, error, connect, reset: resetSSE } = useSSE();

  const { data: manifests, refetch: refetchList } = useManifestList();
  const { data: manifest, refetch: refetchManifest, isLoading: isManifestLoading } = useManifest(activeManifestId);
  const updateSource = useUpdateSource(activeManifestId || "");
  const approveManifest = useApproveManifest();
  const rejectManifest = useRejectManifest();

  const isComplete = events.some((e) => e.step === "complete");

  const handleGenerate = (manifestId: string, streamUrl: string) => {
    setActiveManifestId(manifestId);
    setShowResults(false);
    connect(streamUrl);
  };

  // When SSE completes, auto-fetch manifest detail and show results
  useEffect(() => {
    if (isComplete && activeManifestId) {
      refetchManifest();
      refetchList();
      setShowResults(true);
    }
  }, [isComplete, activeManifestId, refetchManifest, refetchList]);

  useEffect(() => {
    if (error && activeManifestId) {
      refetchManifest();
      refetchList();
      setShowResults(true);
    }
  }, [error, activeManifestId, refetchManifest, refetchList]);

  const handleSelectManifest = (id: string) => {
    resetSSE();
    setActiveManifestId(id);
    setShowResults(true);
  };

  const handleUpdateSource = (sourceId: string, update: Partial<Source>) => {
    if (!activeManifestId) return;
    updateSource.mutate({ sourceId, update });
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>RARIS — Domain Discovery</h1>
      </header>

      <div className="dashboard-layout">
        {/* Sidebar — Manifest list */}
        <aside className="dashboard-sidebar">
          <DomainInputPanel onGenerate={handleGenerate} isGenerating={isConnected} />

          {manifests && manifests.length > 0 && (
            <div className="panel manifest-list-panel">
              <h2>Manifests ({manifests.length})</h2>
              <ul>
                {manifests.map((m) => (
                  <li
                    key={m.id}
                    className={m.id === activeManifestId ? "active" : ""}
                    onClick={() => handleSelectManifest(m.id)}
                  >
                    <div className="manifest-list-item">
                      <strong>{m.domain}</strong>
                      <div className="manifest-list-meta">
                        <span className={`badge badge-${m.status === "approved" ? "success" : m.status === "generating" ? "active" : "warning"}`}>
                          {m.status.replace("_", " ")}
                        </span>
                        <span className="text-muted">{m.programs_count} programs</span>
                        {m.coverage_score > 0 && (
                          <span className="text-muted">{(m.coverage_score * 100).toFixed(0)}%</span>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>

        {/* Main content */}
        <main className="dashboard-main">
          {/* Agent progress — show when generating */}
          {(isConnected || events.length > 0 || error) && (
            <AgentProgressPanel events={events} isConnected={isConnected} error={error} />
          )}

          {/* View Results prompt after completion */}
          {isComplete && !showResults && (
            <div className="panel complete-prompt">
              <p>Discovery complete.</p>
              <button onClick={() => setShowResults(true)}>View Results</button>
            </div>
          )}

          {/* Loading state */}
          {showResults && isManifestLoading && (
            <div className="panel empty-state-panel">
              <p className="text-muted">Loading manifest...</p>
            </div>
          )}

          {/* Manifest detail */}
          {showResults && !isManifestLoading && manifest && (
            <div className="manifest-results">
              <ManifestSummaryCard manifest={manifest} />

              <ProgramsTable programs={manifest.programs} />

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
            </div>
          )}

          {/* Empty state */}
          {!showResults && !isConnected && events.length === 0 && (
            <div className="panel empty-state-panel">
              <p className="text-muted">
                Enter a regulatory domain above to begin discovery, or select a previous manifest from the list.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
