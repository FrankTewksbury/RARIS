import { useState } from "react";
import type { GenerateResponse } from "../types/manifest";

interface Props {
  onGenerate: (manifestId: string, streamUrl: string) => void;
  isGenerating: boolean;
}

const LLM_PROVIDERS = ["openai", "anthropic", "gemini"];

export function DomainInputPanel({ onGenerate, isGenerating }: Props) {
  const [domain, setDomain] = useState("");
  const [provider, setProvider] = useState("openai");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim()) return;
    setError(null);

    try {
      const response = await fetch("/api/manifests/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain_description: domain,
          llm_provider: provider,
        }),
      });
      if (!response.ok) throw new Error("Generation request failed");
      const data: GenerateResponse = await response.json();
      onGenerate(data.manifest_id, data.stream_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  return (
    <div className="panel domain-input-panel">
      <h2>Domain Discovery</h2>
      <form onSubmit={handleSubmit}>
        <textarea
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="Describe the regulatory domain to discover (e.g., 'All US Insurance regulation — federal + all 50 states')"
          rows={4}
          disabled={isGenerating}
        />
        <div className="form-row">
          <label>
            LLM Provider:
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              disabled={isGenerating}
            >
              {LLM_PROVIDERS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={isGenerating || !domain.trim()}>
            {isGenerating ? "Generating..." : "Generate Manifest"}
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </form>
    </div>
  );
}
