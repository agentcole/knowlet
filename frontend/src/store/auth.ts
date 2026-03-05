import { create } from "zustand";
import type { User, Membership } from "@/types";
import { DEFAULT_LANGUAGE } from "@/constants/languages";

interface AuthState {
  user: User | null;
  memberships: Membership[];
  currentTenantId: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, memberships: Membership[]) => void;
  setUser: (user: User) => void;
  setTenant: (tenantId: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  memberships: [],
  currentTenantId: localStorage.getItem("tenant_id"),
  isAuthenticated: !!localStorage.getItem("access_token"),

  setAuth: (user, memberships) => {
    const normalizedUser = {
      ...user,
      default_language: user.default_language || DEFAULT_LANGUAGE,
    };
    const storedTenantId = localStorage.getItem("tenant_id");
    const validTenantIds = new Set(memberships.map((membership) => membership.tenant_id));
    const tenantId =
      storedTenantId && validTenantIds.has(storedTenantId)
        ? storedTenantId
        : memberships[0]?.tenant_id || null;

    if (tenantId) {
      localStorage.setItem("tenant_id", tenantId);
    } else {
      localStorage.removeItem("tenant_id");
    }

    set({
      user: normalizedUser,
      memberships,
      currentTenantId: tenantId,
      isAuthenticated: true,
    });
  },

  setUser: (user) => {
    const normalizedUser = {
      ...user,
      default_language: user.default_language || DEFAULT_LANGUAGE,
    };
    set((state) => ({ ...state, user: normalizedUser }));
  },

  setTenant: (tenantId) => {
    localStorage.setItem("tenant_id", tenantId);
    set({ currentTenantId: tenantId });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("tenant_id");
    set({ user: null, memberships: [], currentTenantId: null, isAuthenticated: false });
  },
}));
