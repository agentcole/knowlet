import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { authApi } from "@/api/auth";
import { useAuthStore } from "@/store/auth";

export function useAuth() {
  const { isAuthenticated, setAuth, logout } = useAuthStore();

  const { data, isLoading, error } = useQuery({
    queryKey: ["me"],
    queryFn: () => authApi.me().then((r) => r.data),
    enabled: isAuthenticated,
    retry: false,
  });

  useEffect(() => {
    if (data) {
      setAuth(data.user, data.memberships);
    }
  }, [data, setAuth]);

  useEffect(() => {
    if (error) {
      logout();
    }
  }, [error, logout]);

  return { isLoading: isAuthenticated && isLoading, isAuthenticated };
}
