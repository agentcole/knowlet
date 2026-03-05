import api from "./client";
import type { User, Membership } from "@/types";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
}

export interface MeResponse {
  user: User;
  memberships: Membership[];
}

export const authApi = {
  register: (data: {
    email: string;
    password: string;
    full_name: string;
    tenant_name: string;
    default_language?: string;
  }) =>
    api.post<TokenResponse>("/auth/register", data),

  login: (data: { email: string; password: string }) =>
    api.post<TokenResponse>("/auth/login", data),

  me: () => api.get<MeResponse>("/auth/me"),

  updatePreferences: (data: { default_language: string }) =>
    api.patch<User>("/auth/preferences", data),
};
