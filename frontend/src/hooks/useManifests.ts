import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { manifestsApi } from "../api/manifests";
import type { GenerateRequest, ReviewRequest, Source } from "../types/manifest";

export function useManifestList() {
  return useQuery({
    queryKey: ["manifests"],
    queryFn: () => manifestsApi.list(),
    select: (data) => data.manifests,
  });
}

export function useManifest(id: string | undefined) {
  return useQuery({
    queryKey: ["manifests", id],
    queryFn: () => manifestsApi.get(id!),
    enabled: !!id,
  });
}

export function useGenerateManifest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (req: GenerateRequest) => manifestsApi.generate(req),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["manifests"] }),
  });
}

export function useUpdateSource(manifestId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, update }: { sourceId: string; update: Partial<Source> }) =>
      manifestsApi.updateSource(manifestId, sourceId, update),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["manifests", manifestId] }),
  });
}

export function useApproveManifest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, review }: { id: string; review: ReviewRequest }) =>
      manifestsApi.approve(id, review),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["manifests"] }),
  });
}

export function useRejectManifest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, review }: { id: string; review: ReviewRequest }) =>
      manifestsApi.reject(id, review),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["manifests"] }),
  });
}
