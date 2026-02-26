import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { retrievalApi } from "../api/retrieval";
import type { AnalysisRequest, QueryRequest } from "../types/retrieval";

export function useSubmitQuery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: QueryRequest) => retrievalApi.query(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["corpus"] });
    },
  });
}

export function useQueryResult(queryId: string | undefined) {
  return useQuery({
    queryKey: ["query", queryId],
    queryFn: () => retrievalApi.getQuery(queryId!),
    enabled: !!queryId,
  });
}

export function useSubmitAnalysis() {
  return useMutation({
    mutationFn: (request: AnalysisRequest) => retrievalApi.analysis(request),
  });
}

export function useAnalysisResult(analysisId: string | undefined) {
  return useQuery({
    queryKey: ["analysis", analysisId],
    queryFn: () => retrievalApi.getAnalysis(analysisId!),
    enabled: !!analysisId,
  });
}

export function useCorpusStats() {
  return useQuery({
    queryKey: ["corpus", "stats"],
    queryFn: () => retrievalApi.corpusStats(),
    refetchInterval: 30000,
  });
}

export function useCorpusSources() {
  return useQuery({
    queryKey: ["corpus", "sources"],
    queryFn: () => retrievalApi.corpusSources(),
    refetchInterval: 30000,
  });
}

export function useCitation(chunkId: string | undefined) {
  return useQuery({
    queryKey: ["citation", chunkId],
    queryFn: () => retrievalApi.getCitation(chunkId!),
    enabled: !!chunkId,
  });
}
