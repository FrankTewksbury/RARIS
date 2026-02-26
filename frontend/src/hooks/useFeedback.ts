import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { feedbackApi } from "../api/feedback";
import type { ResolveFeedbackRequest, SubmitFeedbackRequest } from "../types/feedback";

export function useFeedbackList(status?: string, feedbackType?: string) {
  return useQuery({
    queryKey: ["feedback", status, feedbackType],
    queryFn: () => feedbackApi.list({ status, feedback_type: feedbackType }),
    refetchInterval: 10000,
  });
}

export function useFeedback(id: string | undefined) {
  return useQuery({
    queryKey: ["feedback", id],
    queryFn: () => feedbackApi.get(id!),
    enabled: !!id,
  });
}

export function useSubmitFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: SubmitFeedbackRequest) => feedbackApi.submit(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feedback"] });
      queryClient.invalidateQueries({ queryKey: ["accuracy"] });
    },
  });
}

export function useResolveFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, request }: { id: string; request: ResolveFeedbackRequest }) =>
      feedbackApi.resolve(id, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feedback"] });
      queryClient.invalidateQueries({ queryKey: ["accuracy"] });
    },
  });
}

export function useCurationQueue(status?: string) {
  return useQuery({
    queryKey: ["curation-queue", status],
    queryFn: () => feedbackApi.listQueue({ status }),
    refetchInterval: 10000,
  });
}

export function useProcessQueueItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => feedbackApi.processQueueItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["curation-queue"] }),
  });
}

export function useChangeList(status?: string) {
  return useQuery({
    queryKey: ["changes", status],
    queryFn: () => feedbackApi.listChanges({ status }),
    refetchInterval: 15000,
  });
}

export function useTriggerMonitor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => feedbackApi.triggerMonitor(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["changes"] }),
  });
}

export function useAccuracyDashboard() {
  return useQuery({
    queryKey: ["accuracy", "dashboard"],
    queryFn: () => feedbackApi.dashboard(),
    refetchInterval: 30000,
  });
}
