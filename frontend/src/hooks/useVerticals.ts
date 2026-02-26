import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { verticalsApi } from "../api/verticals";
import type { CreateVerticalRequest } from "../types/vertical";

export function useVerticalList() {
  return useQuery({
    queryKey: ["verticals"],
    queryFn: () => verticalsApi.list(),
    refetchInterval: 10000,
  });
}

export function useVertical(id: string | undefined) {
  return useQuery({
    queryKey: ["verticals", id],
    queryFn: () => verticalsApi.get(id!),
    enabled: !!id,
    refetchInterval: 5000,
  });
}

export function useVerticalStatus(id: string | undefined) {
  return useQuery({
    queryKey: ["verticals", id, "status"],
    queryFn: () => verticalsApi.status(id!),
    enabled: !!id,
    refetchInterval: 5000,
  });
}

export function useCreateVertical() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: CreateVerticalRequest) => verticalsApi.create(request),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["verticals"] }),
  });
}

export function useTriggerDiscovery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => verticalsApi.discover(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["verticals"] }),
  });
}

export function useTriggerAcquisition() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => verticalsApi.acquire(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["verticals"] }),
  });
}

export function useTriggerIngestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => verticalsApi.ingest(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["verticals"] }),
  });
}
