import type { AgentStepEvent } from "../types/manifest";

const STEPS = [
  { key: "landscape_mapper", label: "Landscape" },
  { key: "source_hunter", label: "Sources" },
  { key: "relationship_mapper", label: "Relationships" },
  { key: "coverage_assessor", label: "Coverage" },
  { key: "manifest_generator", label: "Manifest" },
];

interface Props {
  events: AgentStepEvent[];
  isConnected: boolean;
}

export function AgentProgressPanel({ events, isConnected }: Props) {
  const completedSteps = new Set(
    events.filter((e) => e.status === "complete").map((e) => e.step)
  );
  const currentStep = events
    .filter((e) => e.status === "running")
    .map((e) => e.step)
    .pop();

  const progressEvents = events.filter((e) => e.step === "progress");
  const progressEvent = progressEvents.length > 0 ? progressEvents[progressEvents.length - 1] : undefined;
  const latestProgressEvent = progressEvents.length > 0 ? progressEvents[progressEvents.length - 1] : undefined;
  const isComplete = events.some((e) => e.step === "complete");

  // #region agent log
  if (
    progressEvent &&
    latestProgressEvent &&
    (
      progressEvent.sources_found !== latestProgressEvent.sources_found ||
      progressEvent.bodies_processed !== latestProgressEvent.bodies_processed
    )
  ) {
    fetch("http://127.0.0.1:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Debug-Session-Id": "2fe1ec",
      },
      body: JSON.stringify({
        sessionId: "2fe1ec",
        runId: "sse-stream",
        hypothesisId: "H1",
        location: "frontend/src/components/AgentProgressPanel.tsx:progressSelection",
        message: "Displayed progress differs from latest progress event",
        data: {
          displayed_sources_found: progressEvent.sources_found ?? null,
          displayed_bodies_processed: progressEvent.bodies_processed ?? null,
          latest_sources_found: latestProgressEvent.sources_found ?? null,
          latest_bodies_processed: latestProgressEvent.bodies_processed ?? null,
          progress_event_count: progressEvents.length,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
  }
  // #endregion

  if (events.length === 0 && !isConnected) return null;

  return (
    <div className="panel agent-progress-panel">
      <h2>Agent Progress {isConnected && <span className="badge badge-active">LIVE</span>}</h2>

      <div className="progress-steps">
        {STEPS.map(({ key, label }) => {
          let status = "pending";
          if (completedSteps.has(key)) status = "complete";
          else if (currentStep === key) status = "running";

          return (
            <div key={key} className={`step step-${status}`}>
              <span className="step-indicator">
                {status === "complete" ? "\u2713" : status === "running" ? "\u25CB" : "\u2022"}
              </span>
              <span className="step-label">{label}</span>
            </div>
          );
        })}
      </div>

      {progressEvent && (
        <p className="progress-stats">
          Sources found: {progressEvent.sources_found ?? 0} |
          Bodies processed: {progressEvent.bodies_processed ?? 0} /
          {progressEvent.total_bodies ?? 0}
        </p>
      )}

      {isComplete && <p className="complete-msg">Discovery complete.</p>}

      <div className="event-log">
        {events
          .filter((e) => e.message)
          .map((e, i) => (
            <div key={i} className="event-entry">
              <span className="event-step">[{e.step}]</span> {e.message}
            </div>
          ))}
      </div>
    </div>
  );
}
