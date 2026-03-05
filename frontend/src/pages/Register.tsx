import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "@/api/auth";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES } from "@/constants/languages";

export function RegisterPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    tenant_name: "",
    default_language: DEFAULT_LANGUAGE,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await authApi.register(form);
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);

      const meRes = await authApi.me();
      setAuth(meRes.data.user, meRes.data.memberships);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Create your account</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-md">{error}</div>
            )}
            <div>
              <label className="text-sm font-medium">Full Name</label>
              <Input value={form.full_name} onChange={update("full_name")} required />
            </div>
            <div>
              <label className="text-sm font-medium">Email</label>
              <Input type="email" value={form.email} onChange={update("email")} required />
            </div>
            <div>
              <label className="text-sm font-medium">Password</label>
              <Input type="password" value={form.password} onChange={update("password")} required minLength={6} />
            </div>
            <div>
              <label className="text-sm font-medium">Company / Team Name</label>
              <Input value={form.tenant_name} onChange={update("tenant_name")} required placeholder="Your organization name" />
            </div>
            <div>
              <label className="text-sm font-medium">Default Language</label>
              <select
                className="mt-1 w-full text-sm border border-border rounded-md px-3 py-2 bg-background"
                value={form.default_language}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, default_language: e.target.value }))
                }
              >
                {SUPPORTED_LANGUAGES.map((language) => (
                  <option key={language.code} value={language.code}>
                    {language.label}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating account..." : "Create account"}
            </Button>
            <p className="text-sm text-center text-muted-foreground">
              Already have an account?{" "}
              <Link to="/login" className="text-primary hover:underline">Sign in</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
