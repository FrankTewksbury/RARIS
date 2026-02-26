import { useCallback, useRef, useState } from "react";
import { QueryInput } from "../components/retrieval/QueryInput";
import { ResponsePanel } from "../components/retrieval/ResponsePanel";
import { CitationExplorer } from "../components/retrieval/CitationExplorer";
import { SourcesPanel } from "../components/retrieval/SourcesPanel";
import { AnalysisView } from "../components/retrieval/AnalysisView";
import { useSubmitQuery } from "../hooks/useRetrieval";
import { streamQuery } from "../api/retrieval";
import type { Citation, QueryResponse, SearchFilters } from "../types/retrieval";

export function QueryInterface() {
  const [responseText, setResponseText] = useState("");
  const [depthName, setDepthName] = useState("");
  const [tokenCount, setTokenCount] = useState(0);
  const [sourcesCount, setSourcesCount] = useState(0);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [useStreaming, setUseStreaming] = useState(true);

  const abortRef = useRef<AbortController | null>(null);
  const submitQuery = useSubmitQuery();

  const handleSubmit = useCallback(
    (query: string, depth: number, filters?: SearchFilters) => {
      // Reset state
      setResponseText("");
      setCitations([]);
      setDepthName("");
      setTokenCount(0);
      setSourcesCount(0);
      setSelectedCitation(null);

      if (useStreaming) {
        setIsStreaming(true);
        abortRef.current = streamQuery(
          { query, depth, filters },
          (token) => {
            setResponseText((prev) => prev + token);
          },
          (response: QueryResponse) => {
            setResponseText(response.response_text);
            setCitations(response.citations);
            setDepthName(response.depth_name);
            setTokenCount(response.token_count);
            setSourcesCount(response.sources_count);
            setIsStreaming(false);
          },
          (error) => {
            setResponseText(`Error: ${error}`);
            setIsStreaming(false);
          },
        );
      } else {
        submitQuery.mutate(
          { query, depth, filters },
          {
            onSuccess: (data) => {
              setResponseText(data.response_text);
              setCitations(data.citations);
              setDepthName(data.depth_name);
              setTokenCount(data.token_count);
              setSourcesCount(data.sources_count);
            },
            onError: (err) => {
              setResponseText(`Error: ${err.message}`);
            },
          },
        );
      }
    },
    [useStreaming, submitQuery],
  );

  const handleCancel = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
  };

  return (
    <div className="dashboard">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Query Interface</h2>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={useStreaming}
            onChange={(e) => setUseStreaming(e.target.checked)}
          />
          Stream response
        </label>
      </div>

      <QueryInput
        onSubmit={handleSubmit}
        isLoading={submitQuery.isPending}
        isStreaming={isStreaming}
        onCancel={handleCancel}
      />

      <ResponsePanel
        responseText={responseText}
        depthName={depthName}
        tokenCount={tokenCount}
        sourcesCount={sourcesCount}
        citations={citations}
        isStreaming={isStreaming}
        onCitationClick={setSelectedCitation}
      />

      <div style={{ display: "grid", gridTemplateColumns: selectedCitation ? "1fr 1fr" : "1fr", gap: "1rem" }}>
        <SourcesPanel citations={citations} onCitationClick={setSelectedCitation} />
        {selectedCitation && (
          <CitationExplorer
            citation={selectedCitation}
            onClose={() => setSelectedCitation(null)}
          />
        )}
      </div>

      <AnalysisView />
    </div>
  );
}
