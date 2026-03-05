import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { tenantsApi } from "@/api/tenants";
import type { TenantRole } from "@/types";

export function useTenantMembers() {
  return useQuery({
    queryKey: ["tenant-members"],
    queryFn: () => tenantsApi.listMembers().then((response) => response.data),
  });
}

export function useInviteMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { email: string; role: TenantRole }) =>
      tenantsApi.inviteMember(data).then((response) => response.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-members"] });
    },
  });
}

export function useUpdateMemberRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: TenantRole }) =>
      tenantsApi.updateMemberRole(userId, { role }).then((response) => response.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-members"] });
    },
  });
}

export function useRemoveMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => tenantsApi.removeMember(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-members"] });
    },
  });
}
