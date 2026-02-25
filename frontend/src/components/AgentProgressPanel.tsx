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

  const progressEvent = events.find((e) => e.step === "progress");
  const isComplete = events.some((e) => e.step === "complete");

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
