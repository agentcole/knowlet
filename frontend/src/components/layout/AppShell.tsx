import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { authApi } from "@/api/auth";
import { DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES } from "@/constants/languages";
import {
  FileText,
  BookOpen,
  Mic,
  MessageSquare,
  LayoutDashboard,
  LogOut,
  ChevronDown,
} from "lucide-react";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/documents", label: "Documents", icon: FileText },
  { path: "/wiki", label: "Wiki", icon: BookOpen },
  { path: "/meetings", label: "Meetings", icon: Mic },
  { path: "/chat", label: "Chat", icon: MessageSquare },
];

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, memberships, currentTenantId, setTenant, setUser, logout } = useAuthStore();
  const [isUpdatingLanguage, setIsUpdatingLanguage] = useState(false);
  const [languageError, setLanguageError] = useState("");

  const currentTenant = memberships.find((m) => m.tenant_id === currentTenantId);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleLanguageChange = async (language: string) => {
    if (!user || language === user.default_language || isUpdatingLanguage) return;
    setLanguageError("");
    setIsUpdatingLanguage(true);
    try {
      const { data } = await authApi.updatePreferences({ default_language: language });
      setUser(data);
    } catch (err: any) {
      setLanguageError(err.response?.data?.detail || "Failed to update language");
    } finally {
      setIsUpdatingLanguage(false);
    }
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-muted/30 flex flex-col">
        <div className="p-4 border-b border-border">
          <h1 className="text-lg font-bold">Knowledge Base</h1>
          {currentTenant && (
            <p className="text-sm text-muted-foreground mt-1">{currentTenant.tenant_name}</p>
          )}
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground hover:bg-accent"
                }`}
              >
                <Icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-border">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{user?.full_name}</p>
              <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
            </div>
            <Button variant="ghost" size="icon" onClick={handleLogout}>
              <LogOut size={18} />
            </Button>
          </div>

          {memberships.length > 1 && (
            <select
              className="mt-2 w-full text-xs border border-border rounded p-1"
              value={currentTenantId || ""}
              onChange={(e) => setTenant(e.target.value)}
            >
              {memberships.map((m) => (
                <option key={m.tenant_id} value={m.tenant_id}>
                  {m.tenant_name}
                </option>
              ))}
            </select>
          )}

          <div className="mt-2">
            <label className="text-xs text-muted-foreground">Default Language</label>
            <select
              className="mt-1 w-full text-xs border border-border rounded p-1"
              value={user?.default_language || DEFAULT_LANGUAGE}
              disabled={!user || isUpdatingLanguage}
              onChange={(e) => handleLanguageChange(e.target.value)}
            >
              {SUPPORTED_LANGUAGES.map((language) => (
                <option key={language.code} value={language.code}>
                  {language.label}
                </option>
              ))}
            </select>
            {languageError && (
              <p className="mt-1 text-xs text-destructive">{languageError}</p>
            )}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
