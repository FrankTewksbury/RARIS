import { useState } from "react";
import { ANALYSIS_TYPES } from "../../types/retrieval";
import type { AnalysisResponse, SearchFilters } from "../../types/retrieval";
import { useSubmitAnalysis } from "../../hooks/useRetrieval";

export function AnalysisView() {
  const [analysisType, setAnalysisType] = useState("gap");
  const [primaryText, setPrimaryText] = useState("");
  const [depth, setDepth] = useState(3);
  const [jurisdiction, setJurisdiction] = useState("");
  const [result, setResult] = useState<AnalysisResponse | null>(null);

  const mutation = useSubmitAnalysis();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!primaryText.trim()) return;

    const filters: SearchFilters = {};
    if (jurisdiction) filters.jurisdiction = jurisdiction.split(",").map((s) => s.trim());

    const response = await mutation.mutateAsync({
      analysis_type: analysisType,
      primary_text: primaryText,
      depth,
      filters: Object.keys(filters).length > 0 ? filters : undefined,
    });
    setResult(response);
  };

  const severityColor = (severity: string) => {
    switch (severity) {
      case "high": return "badge-danger";
      case "medium": return "badge-warning";
      case "low": return "badge-success";
      default: return "";
    }
  };

  return (
    <div className="panel">
      <h3>Cross-Corpus Analysis</h3>

      <form onSubmit={handleSubmit}>
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
          <select value={analysisType} onChange={(e) => setAnalysisType(e.target.value)}>
            {ANALYSIS_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
            <option value={1}>Depth 1</option>
            <option value={2}>Depth 2</option>
            <option value={3}>Depth 3</option>
            <option value={4}>Depth 4</option>
          </select>
          <input
            placeholder="Jurisdiction filter (optional)"
            value={jurisdiction}
            onChange={(e) => setJurisdiction(e.target.value)}
            style={{ flex: 1 }}
          />
        </div>

        <textarea
          value={primaryText}
          onChange={(e) => setPrimaryText(e.target.value)}
          placeholder="Paste document text or policy to analyze..."
          rows={5}
          style={{ width: "100%", marginBottom: "0.75rem", resize: "vertical" }}
        />

        <button type="submit" disabled={!primaryText.trim() || mutation.isPending}>
          {mutation.isPending ? "Analyzing..." : "Run Analysis"}
        </button>
      </form>

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <h4 style={{ margin: 0 }}>
              {ANALYSIS_TYPES.find((t) => t.value === result.analysis_type)?.label}
            </h4>
            {result.coverage_score !== null && (
              <span className="badge">
                Coverage: {(result.coverage_score * 100).toFixed(0)}%
              </span>
            )}
          </div>

          {result.findings.length > 0 && (
            <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "1rem" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Severity</th>
                  <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Category</th>
                  <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Description</th>
                  <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {result.findings.map((f, i) => (
                  <tr key={i}>
                    <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>
                      <span className={`badge ${severityColor(f.severity)}`}>{f.severity}</span>
                    </td>
                    <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>{f.category}</td>
                    <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>{f.description}</td>
                    <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border)" }}>{f.recommendation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {result.summary && (
            <div>
              <h4>Summary</h4>
              <p style={{ whiteSpace: "pre-wrap" }}>{result.summary}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
