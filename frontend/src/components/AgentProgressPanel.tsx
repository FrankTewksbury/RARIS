import type { AgentStepEvent } from "../types/manifest";

interface Props {
  events: AgentStepEvent[];
  isConnected: boolean;
}

export function AgentProgressPanel({ events, isConnected }: Props) {
  const isComplete = events.some((e) => e.step === "complete");

  // Sector events (V5)
  const sectorEvents = events.filter((e) => (e.step as string).startsWith("sector:"));
  const expandEvents = events.filter((e) => (e.step as string).startsWith("expand:"));
  const l1Done = events.some((e) => e.step === "l1_assembly");

  if (events.length === 0 && !isConnected) return null;

  return (
    <div className="panel agent-progress-panel">
      <h2>Agent Progress {isConnected && <span className="badge badge-active">LIVE</span>}</h2>

      {/* Sector progress (L1) */}
      {(sectorEvents.length > 0 || isConnected) && (
        <div className="progress-steps">
          {sectorEvents.map((e, i) => {
            const status = e.status === "complete" ? "complete" : e.status === "failed" ? "failed" : "running";
            return (
              <div key={i} className={`step step-${status}`}>
                <span className="step-indicator">
                  {status === "complete" ? "✓" : status === "failed" ? "✗" : "○"}
                </span>
                <span className="step-label">{e.message}</span>
              </div>
            );
          })}
          {l1Done && (
            <div className="step step-complete">
              <span className="step-indicator">✓</span>
              <span className="step-label">
                {events.find((e) => e.step === "l1_assembly")?.message}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Entity expansion progress (L2) */}
      {expandEvents.length > 0 && (
        <div className="expand-stats">
          <p>
            Expanding entities: {expandEvents.filter((e) => e.status === "complete").length} /
            {expandEvents.length} done
          </p>
        </div>
      )}

      {isComplete && <p className="complete-msg">Discovery complete.</p>}

      {/* Full event log */}
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
