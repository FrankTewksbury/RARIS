import type { Citation } from "../../types/retrieval";

interface Props {
  citations: Citation[];
  onCitationClick: (citation: Citation) => void;
}

interface GroupedSource {
  source_id: string;
  regulatory_body: string;
  authority_level: string;
  source_url: string;
  sections: string[];
  confidence: number;
}

export function SourcesPanel({ citations, onCitationClick }: Props) {
  if (citations.length === 0) return null;

  // Group citations by source_id
  const groupedMap = new Map<string, GroupedSource>();
  for (const c of citations) {
    const existing = groupedMap.get(c.source_id);
    if (existing) {
      if (!existing.sections.includes(c.section_path)) {
        existing.sections.push(c.section_path);
      }
      existing.confidence = Math.max(existing.confidence, c.confidence);
    } else {
      groupedMap.set(c.source_id, {
        source_id: c.source_id,
        regulatory_body: c.regulatory_body,
        authority_level: c.authority_level,
        source_url: c.source_url,
        sections: [c.section_path],
        confidence: c.confidence,
      });
    }
  }

  // Group by regulatory body
  const byBody = new Map<string, GroupedSource[]>();
  for (const source of groupedMap.values()) {
    const body = source.regulatory_body || "Unknown";
    const list = byBody.get(body) || [];
    list.push(source);
    byBody.set(body, list);
  }

  return (
    <div className="panel">
      <h3>Sources ({groupedMap.size})</h3>

      {Array.from(byBody.entries()).map(([body, sources]) => (
        <div key={body} style={{ marginBottom: "1rem" }}>
          <h4 style={{ marginBottom: "0.5rem", color: "var(--text-muted)" }}>{body}</h4>
          {sources.map((source) => (
            <div
              key={source.source_id}
              style={{
                padding: "0.5rem",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>{source.source_id}</div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                  {source.sections.map((s, i) => (
                    <span key={i}>
                      {i > 0 && ", "}
                      <span
                        style={{ cursor: "pointer", textDecoration: "underline" }}
                        onClick={() => {
                          const cit = citations.find(
                            (c) => c.source_id === source.source_id && c.section_path === s
                          );
                          if (cit) onCitationClick(cit);
                        }}
                      >
                        {s}
                      </span>
                    </span>
                  ))}
                </div>
              </div>
              <span
                className={`badge ${source.authority_level === "binding" ? "badge-danger" : "badge-success"}`}
              >
                {source.authority_level}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
