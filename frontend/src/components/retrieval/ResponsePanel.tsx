import type { Citation } from "../../types/retrieval";

interface Props {
  responseText: string;
  depthName: string;
  tokenCount: number;
  sourcesCount: number;
  citations: Citation[];
  isStreaming: boolean;
  onCitationClick: (citation: Citation) => void;
}

/** Regex matching inline citations like [src-001 §1026.19(e)] */
const CITATION_REGEX = /\[([^\]]+?)\s+§([^\]]+)\]/g;

function renderResponseWithCitations(
  text: string,
  citations: Citation[],
  onCitationClick: (citation: Citation) => void,
) {
  const parts: (string | JSX.Element)[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(CITATION_REGEX)) {
    const fullMatch = match[0];
    const sourceId = match[1];
    const section = match[2];
    const idx = match.index!;

    if (idx > lastIndex) {
      parts.push(text.slice(lastIndex, idx));
    }

    const citation = citations.find(
      (c) => c.source_id === sourceId || c.section_path.includes(section)
    );

    parts.push(
      <span
        key={idx}
        className="citation-link"
        onClick={() => citation && onCitationClick(citation)}
        title={citation ? `${citation.document_title} — ${citation.section_path}` : fullMatch}
        style={{
          color: "var(--primary)",
          cursor: citation ? "pointer" : "default",
          textDecoration: "underline",
          fontWeight: 500,
        }}
      >
        {fullMatch}
      </span>
    );

    lastIndex = idx + fullMatch.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

export function ResponsePanel({
  responseText,
  depthName,
  tokenCount,
  sourcesCount,
  citations,
  isStreaming,
  onCitationClick,
}: Props) {
  if (!responseText && !isStreaming) return null;

  return (
    <div className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Response</h3>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          {depthName && <span className="badge">{depthName}</span>}
          {sourcesCount > 0 && (
            <span className="badge badge-success">{sourcesCount} sources</span>
          )}
          {tokenCount > 0 && (
            <span className="text-muted">{tokenCount} tokens</span>
          )}
        </div>
      </div>

      <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
        {renderResponseWithCitations(responseText, citations, onCitationClick)}
        {isStreaming && (
          <span className="streaming-cursor" style={{ animation: "blink 1s infinite" }}>
            |
          </span>
        )}
      </div>
    </div>
  );
}
