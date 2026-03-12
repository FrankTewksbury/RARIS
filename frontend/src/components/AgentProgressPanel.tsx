import type { AgentStepEvent } from "../types/manifest";

interface Props {
  events: AgentStepEvent[];
  isConnected: boolean;
  error?: string | null;
  apiCalls?: number;
  maxApiCalls?: number;
  lastCheckpoint?: AgentStepEvent | null;
  manifestId?: string;
  hasCheckpoint?: boolean;
  onResume?: () => void;
}

export function AgentProgressPanel({ events, isConnected, error, apiCalls = 0, maxApiCalls = 3000, lastCheckpoint, hasCheckpoint, onResume }: Props) {
  const isComplete = events.some((e) => e.step === "complete");

  // Prompt-level events (multi-prompt L1 loop)
  const promptStartEvents = events.filter((e) => (e.step as string).startsWith("prompt:") && (e.step as string).endsWith(":start"));
  const promptCompleteEvents = events.filter((e) => (e.step as string).startsWith("prompt:") && (e.step as string).endsWith(":complete"));
  const promptTotal: number = (promptStartEvents[0] as (AgentStepEvent & { prompt_total?: number }) | undefined)?.prompt_total ?? 0;
  const isMultiPrompt = promptTotal > 1;

  // Sector events (V5)
  const sectorEvents = events.filter((e) => (e.step as string).startsWith("sector:"));
  const expandEvents = events.filter((e) => (e.step as string).startsWith("expand:"));
  const checkpointEvents = events.filter((e) => (e.step as string).startsWith("checkpoint:"));
  const l1Done = events.some((e) => e.step === "l1_assembly");

  if (events.length === 0 && !isConnected) return null;

  const showResumeButton = hasCheckpoint && !isConnected && !isComplete;

  return (
    <div className="panel agent-progress-panel">
      <h2>Agent Progress {isConnected && <span className="badge badge-active">LIVE</span>}</h2>

      {/* API call counter */}
      {(apiCalls > 0 || isConnected) && (
        <div className="api-call-counter">
          API calls: <strong>{apiCalls}</strong> / {maxApiCalls}
          {lastCheckpoint && (
            <span className="checkpoint-badge" title={lastCheckpoint.message}>
              {" "}· sync point saved
            </span>
          )}
        </div>
      )}

      {/* Multi-prompt L1 loop progress */}
      {isMultiPrompt && (
        <div className="prompt-progress">
          <p className="prompt-summary">
            L1 Prompt Loop: {promptCompleteEvents.length}/{promptTotal} passes complete
          </p>
          <div className="progress-steps">
            {Array.from({ length: promptTotal }, (_, i) => {
              const n = i + 1;
              const started = promptStartEvents.some((e) => (e as AgentStepEvent & { prompt_n?: number }).prompt_n === n);
              const completed = promptCompleteEvents.some((e) => (e as AgentStepEvent & { prompt_n?: number }).prompt_n === n);
              const status = completed ? "complete" : started ? "running" : "pending";
              return (
                <div key={n} className={`step step-${status}`}>
                  <span className="step-indicator">
                    {status === "complete" ? "✓" : status === "running" ? "○" : "·"}
                  </span>
                  <span className="step-label">Prompt {n} — {status}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

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
            {apiCalls > 0 && (
              <span className="api-calls-inline"> · API calls: {apiCalls} / {maxApiCalls}</span>
            )}
          </p>
        </div>
      )}

      {/* Checkpoint sync points */}
      {checkpointEvents.length > 0 && (
        <div className="checkpoint-list">
          {checkpointEvents.map((e, i) => (
            <div key={i} className="step step-checkpoint">
              <span className="step-indicator">⊙</span>
              <span className="step-label">{e.message}</span>
            </div>
          ))}
        </div>
      )}

      {isComplete && <p className="complete-msg">Discovery complete.</p>}
      {error && <p className="error">{error}</p>}

      {/* Resume button */}
      {showResumeButton && onResume && (
        <div className="resume-action">
          <p className="resume-hint">This run has a saved sync point. You can resume from where it stopped.</p>
          <button className="btn btn-resume" onClick={onResume}>Resume from Checkpoint</button>
        </div>
      )}

      {/* Full event log */}
      <div className="event-log">
        {events
          .filter((e) => e.message)
          .map((e, i) => (
            <div key={i} className={`event-entry${(e.step as string).startsWith("checkpoint:") ? " event-checkpoint" : ""}`}>
              <span className="event-step">[{e.step}]</span> {e.message}
            </div>
          ))}
      </div>
    </div>
  );
}
