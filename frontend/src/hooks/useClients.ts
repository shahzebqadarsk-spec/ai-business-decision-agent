import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/clients";

export function useClients() {
  return useQuery({ queryKey: ["clients"], queryFn: api.listClients });
}

export function useClient(clientId: string | null) {
  return useQuery({
    queryKey: ["client", clientId],
    queryFn: () => api.getClient(clientId as string),
    enabled: clientId !== null,
  });
}

export function useCreateClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.createClient(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["clients"] });
    },
  });
}
