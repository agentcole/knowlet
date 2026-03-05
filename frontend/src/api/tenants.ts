import api from "./client";
import type { TenantMember, TenantRole } from "@/types";

export const tenantsApi = {
  listMembers: () => api.get<TenantMember[]>("/tenants/current/members"),

  inviteMember: (data: { email: string; role: TenantRole }) =>
    api.post<TenantMember>("/tenants/current/invite", data),

  updateMemberRole: (userId: string, data: { role: TenantRole }) =>
    api.patch<TenantMember>(`/tenants/current/members/${userId}`, data),

  removeMember: (userId: string) => api.delete(`/tenants/current/members/${userId}`),
};
