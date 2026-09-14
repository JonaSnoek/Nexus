import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { UserPlus, AlertCircle } from "lucide-react";
import { setup } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";

export default function SetupPage() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [form, setForm] = useState({
    username: "",
    display_name: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function updateField(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);

    try {
      await setup({
        username: form.username,
        display_name: form.display_name || form.username,
        email: form.email,
        password: form.password,
      });
      await refreshUser();
      navigate("/chat", { replace: true });
    } catch (err: any) {
      setError(err.message || "Setup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a] px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500">
            <span className="text-lg font-bold text-white">N</span>
          </div>
          <h1 className="text-xl font-semibold text-gray-100">
            Welcome to NEXUS
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Set up your admin account to get started.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-400">
              <AlertCircle size={14} className="shrink-0" />
              {error}
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Username <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => updateField("username", e.target.value)}
              required
              autoFocus
              className="w-full rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-blue-500/50"
              placeholder="admin"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Display Name
            </label>
            <input
              type="text"
              value={form.display_name}
              onChange={(e) => updateField("display_name", e.target.value)}
              className="w-full rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-blue-500/50"
              placeholder="Admin User"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Email <span className="text-red-400">*</span>
            </label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => updateField("email", e.target.value)}
              required
              className="w-full rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-blue-500/50"
              placeholder="admin@example.com"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Password <span className="text-red-400">*</span>
            </label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => updateField("password", e.target.value)}
              required
              className="w-full rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-blue-500/50"
              placeholder="At least 8 characters"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-gray-400">
              Confirm Password <span className="text-red-400">*</span>
            </label>
            <input
              type="password"
              value={form.confirmPassword}
              onChange={(e) => updateField("confirmPassword", e.target.value)}
              required
              className="w-full rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-blue-500/50"
              placeholder="Confirm your password"
            />
          </div>

          <button
            type="submit"
            disabled={loading || !form.username || !form.email || !form.password}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50 disabled:hover:bg-blue-500"
          >
            {loading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <>
                <UserPlus size={16} />
                Create Admin Account
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
