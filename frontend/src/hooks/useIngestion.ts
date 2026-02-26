import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ingestionApi } from "../api/ingestion";

export function useIngestionRun(id: string | undefined) {
  return useQuery({
    queryKey: ["ingestion", id],
    queryFn: () => ingestionApi.get(id!),
    enabled: !!id,
    refetchInterval: 5000,
  });
}

export function useIngestionDocuments(id: string | undefined) {
  return useQuery({
    queryKey: ["ingestion", id, "documents"],
    queryFn: () => ingestionApi.listDocuments(id!),
    enabled: !!id,
    refetchInterval: 5000,
  });
}

export function useDocument(docId: string | undefined) {
  return useQuery({
    queryKey: ["documents", docId],
    queryFn: () => ingestionApi.getDocument(docId!),
    enabled: !!docId,
  });
}

export function useStartIngestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (acquisitionId: string) => ingestionApi.start(acquisitionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ingestion"] }),
  });
}

export function useApproveDocument(ingestionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) => ingestionApi.approveDocument(docId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["ingestion", ingestionId] }),
  });
}

export function useRejectDocument(ingestionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ docId, reason }: { docId: string; reason: string }) =>
      ingestionApi.rejectDocument(docId, reason),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["ingestion", ingestionId] }),
  });
}

export function useIndexStats() {
  return useQuery({
    queryKey: ["index", "stats"],
    queryFn: () => ingestionApi.indexStats(),
    refetchInterval: 30000,
  });
}
