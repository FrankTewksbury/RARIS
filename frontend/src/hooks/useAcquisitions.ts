import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { acquisitionsApi } from "../api/acquisitions";

export function useAcquisitionList() {
  return useQuery({
    queryKey: ["acquisitions"],
    queryFn: () => acquisitionsApi.list(),
    select: (data) => data.acquisitions,
  });
}

export function useAcquisition(id: string | undefined) {
  return useQuery({
    queryKey: ["acquisitions", id],
    queryFn: () => acquisitionsApi.get(id!),
    enabled: !!id,
    refetchInterval: 5000,
  });
}

export function useAcquisitionSources(id: string | undefined) {
  return useQuery({
    queryKey: ["acquisitions", id, "sources"],
    queryFn: () => acquisitionsApi.getSources(id!),
    enabled: !!id,
    select: (data) => data.sources,
    refetchInterval: 5000,
  });
}

export function useStartAcquisition() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (manifestId: string) => acquisitionsApi.start(manifestId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["acquisitions"] }),
  });
}

export function useRetrySource(acquisitionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => acquisitionsApi.retrySource(acquisitionId, sourceId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["acquisitions", acquisitionId] }),
  });
}
