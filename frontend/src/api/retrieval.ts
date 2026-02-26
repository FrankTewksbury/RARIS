import { api } from "./client";
import type {
  AnalysisRequest,
  AnalysisResponse,
  CorpusSourceSummary,
  CorpusStats,
  Citation,
  QueryRequest,
  QueryResponse,
} from "../types/retrieval";

export const retrievalApi = {
  query: (request: QueryRequest) =>
    api.post<QueryResponse>("/query", request),

  getQuery: (queryId: string) =>
    api.get<QueryResponse>(`/query/${queryId}`),

  analysis: (request: AnalysisRequest) =>
    api.post<AnalysisResponse>("/analysis", request),

  getAnalysis: (analysisId: string) =>
    api.get<AnalysisResponse>(`/analysis/${analysisId}`),

  corpusStats: () =>
    api.get<CorpusStats>("/corpus/stats"),

  corpusSources: () =>
    api.get<CorpusSourceSummary[]>("/corpus/sources"),

  getCitation: (chunkId: string) =>
    api.get<Citation>(`/citations/${chunkId}`),
};

/** Start an SSE stream for a query. Returns an EventSource. */
export function streamQuery(
  request: QueryRequest,
  onToken: (token: string) => void,
  onComplete: (response: QueryResponse) => void,
  onError: (error: string) => void,
): AbortController {
  const controller = new AbortController();

  fetch("/api/query/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        onError(err.detail || `Request failed: ${res.status}`);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        onError("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data:")) {
            const jsonStr = line.slice(5).trim();
            if (!jsonStr) continue;
            try {
              const event = JSON.parse(jsonStr);
              if (event.token) {
                onToken(event.token);
              }
              if (event.response) {
                onComplete({
                  query_id: event.query_id || "",
                  query: "",
                  depth: 0,
                  depth_name: "",
                  response_text: event.response,
                  citations: event.citations || [],
                  sources_count: event.sources_count || 0,
                  token_count: event.token_count || 0,
                });
              }
              if (event.message && !event.token && !event.response) {
                // Status event — ignore for now
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError(err.message || "Stream failed");
      }
    });

  return controller;
}
