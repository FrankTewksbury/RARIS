import { useState } from "react";
import { useCreateVertical } from "../../hooks/useVerticals";
import type { ScopeConfig } from "../../types/vertical";

interface Props {
  onCreated: (id: string) => void;
  onCancel: () => void;
}

export function NewVerticalWizard({ onCreated, onCancel }: Props) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [jurisdictions, setJurisdictions] = useState("federal, state");
  const [linesOfBusiness, setLinesOfBusiness] = useState("");
  const [exclusions, setExclusions] = useState("");
  const [llmProvider, setLlmProvider] = useState("openai");
  const [sourceMin, setSourceMin] = useState(100);
  const [sourceMax, setSourceMax] = useState(300);
  const [coverageTarget, setCoverageTarget] = useState(0.85);

  const createMutation = useCreateVertical();

  const scope: ScopeConfig = {
    jurisdictions: jurisdictions.split(",").map((s) => s.trim()).filter(Boolean),
    regulatory_bodies: [],
    lines_of_business: linesOfBusiness.split(",").map((s) => s.trim()).filter(Boolean),
    exclusions: exclusions.split(",").map((s) => s.trim()).filter(Boolean),
  };

  const handleCreate = async () => {
    const result = await createMutation.mutateAsync({
      name,
      domain_description: description,
      scope,
      llm_provider: llmProvider,
      expected_source_count_min: sourceMin,
      expected_source_count_max: sourceMax,
      coverage_target: coverageTarget,
      rate_limit_ms: 2000,
      max_concurrent: 5,
      timeout_seconds: 120,
    });
    onCreated(result.id);
  };

  return (
    <div className="panel" style={{ borderLeft: "3px solid var(--primary)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h3 style={{ margin: 0 }}>New Vertical — Step {step}/3</h3>
        <button onClick={onCancel} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.2rem" }}>
          &times;
        </button>
      </div>

      {step === 1 && (
        <div>
          <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>Vertical Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Mortgage — First-Time Homebuyers"
            style={{ width: "100%", marginBottom: "0.75rem" }}
          />

          <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>Domain Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the regulatory domain in detail..."
            rows={4}
            style={{ width: "100%", marginBottom: "0.75rem", resize: "vertical" }}
          />

          <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>Jurisdictions (comma-separated)</label>
          <input
            value={jurisdictions}
            onChange={(e) => setJurisdictions(e.target.value)}
            style={{ width: "100%", marginBottom: "0.75rem" }}
          />

          <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>Lines of Business (comma-separated)</label>
          <input
            value={linesOfBusiness}
            onChange={(e) => setLinesOfBusiness(e.target.value)}
            placeholder="e.g. mortgage origination, mortgage servicing"
            style={{ width: "100%", marginBottom: "0.75rem" }}
          />

          <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>Exclusions (comma-separated)</label>
          <input
            value={exclusions}
            onChange={(e) => setExclusions(e.target.value)}
            placeholder="e.g. commercial real estate, agricultural lending"
            style={{ width: "100%", marginBottom: "0.75rem" }}
          />

          <button
            onClick={() => setStep(2)}
            disabled={!name.trim() || !description.trim()}
          >
            Next
          </button>
        </div>
      )}

      {step === 2 && (
        <div>
          <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>LLM Provider</label>
          <select value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)} style={{ marginBottom: "0.75rem" }}>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Google Gemini</option>
          </select>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <div>
              <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>Min Sources</label>
              <input type="number" value={sourceMin} onChange={(e) => setSourceMin(Number(e.target.value))} />
            </div>
            <div>
              <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>Max Sources</label>
              <input type="number" value={sourceMax} onChange={(e) => setSourceMax(Number(e.target.value))} />
            </div>
            <div>
              <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>Coverage Target</label>
              <input type="number" step="0.05" min="0" max="1" value={coverageTarget} onChange={(e) => setCoverageTarget(Number(e.target.value))} />
            </div>
          </div>

          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button onClick={() => setStep(1)}>Back</button>
            <button onClick={() => setStep(3)}>Next</button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div>
          <h4>Review</h4>
          <table style={{ width: "100%", marginBottom: "1rem" }}>
            <tbody>
              <tr><td style={{ fontWeight: 600, padding: "0.25rem" }}>Name</td><td style={{ padding: "0.25rem" }}>{name}</td></tr>
              <tr><td style={{ fontWeight: 600, padding: "0.25rem" }}>Description</td><td style={{ padding: "0.25rem" }}>{description.slice(0, 100)}...</td></tr>
              <tr><td style={{ fontWeight: 600, padding: "0.25rem" }}>Jurisdictions</td><td style={{ padding: "0.25rem" }}>{scope.jurisdictions.join(", ")}</td></tr>
              <tr><td style={{ fontWeight: 600, padding: "0.25rem" }}>Lines of Business</td><td style={{ padding: "0.25rem" }}>{scope.lines_of_business.join(", ") || "—"}</td></tr>
              <tr><td style={{ fontWeight: 600, padding: "0.25rem" }}>Exclusions</td><td style={{ padding: "0.25rem" }}>{scope.exclusions.join(", ") || "—"}</td></tr>
              <tr><td style={{ fontWeight: 600, padding: "0.25rem" }}>LLM Provider</td><td style={{ padding: "0.25rem" }}>{llmProvider}</td></tr>
              <tr><td style={{ fontWeight: 600, padding: "0.25rem" }}>Expected Sources</td><td style={{ padding: "0.25rem" }}>{sourceMin}–{sourceMax}</td></tr>
              <tr><td style={{ fontWeight: 600, padding: "0.25rem" }}>Coverage Target</td><td style={{ padding: "0.25rem" }}>{(coverageTarget * 100).toFixed(0)}%</td></tr>
            </tbody>
          </table>

          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button onClick={() => setStep(2)}>Back</button>
            <button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create Vertical"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
