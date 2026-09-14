import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { LogIn, AlertCircle, ExternalLink } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { checkHealth } from "../lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [oidcEnabled, setOidcEnabled] = useState(false);
  const [oidcLoading, setOidcLoading] = useState(true);

  useEffect(() => {
    async function checkOidc() {
      try {
        const health = await checkHealth();
        setOidcEnabled(health.oidc_enabled);
        if (health.setup_required) {
          navigate("/setup", { replace: true });
        }
      } catch {
        // ignore
      } finally {
        setOidcLoading(false);
      }
    }
    checkOidc();
  }, [navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(username, password);
    } catch (err: any) {
      setError(err.message || "Invalid username or password");
    } finally {
      setLoading(false);
    }
  }

  function handleOidcLogin() {
    window.location.href = "/api/auth/oidc/login";
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500">
            <span className="text-lg font-bold text-white">N</span>
          </div>
          <h1 className="text-xl font-semibold text-gray-100">Welcome back</h1>
          <p className="mt-1 text-sm text-gray-500">Sign in to NEXUS</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-400">
              <AlertCircle size={14} className="shrink-0" />
              {error}
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm text-gray-400">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              className="w-full rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-blue-500/50"
              placeholder="Enter your username"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-gray-400">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-blue-500/50"
              placeholder="Enter your password"
            />
          </div>

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50 disabled:hover:bg-blue-500"
          >
            {loading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <>
                <LogIn size={16} />
                Sign In
              </>
            )}
          </button>
        </form>

        {!oidcLoading && oidcEnabled && (
          <>
            <div className="my-4 flex items-center gap-3">
              <div className="h-px flex-1 bg-nexus-border" />
              <span className="text-xs text-gray-500">or</span>
              <div className="h-px flex-1 bg-nexus-border" />
            </div>

            <button
              onClick={handleOidcLogin}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-nexus-border bg-nexus-surface px-4 py-2.5 text-sm text-gray-300 transition-colors hover:bg-nexus-elevated"
            >
              <ExternalLink size={16} />
              SSO Login
            </button>
          </>
        )}
      </div>
    </div>
  );
}
