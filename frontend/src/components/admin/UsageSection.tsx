import { useState, useEffect } from "react";
import { BarChart3, RefreshCw, MessageSquare, Image as ImageIcon, Zap, Activity } from "lucide-react";
import { getDashboard, getUsageSummary } from "../../lib/api";
import type { DashboardStats, UsageSummary } from "../../types";

export default function UsageSection() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  async function loadStats() {
    setLoading(true);
    try {
      const [data, usage] = await Promise.all([getDashboard(), getUsageSummary()]);
      setStats(data);
      setSummary(usage);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  function formatNumber(n: number): string {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(1) + "K";
    return n.toString();
  }

  const maxTokens = stats
    ? Math.max(stats.total_tokens, stats.tokens_today, 1)
    : 1;
  const maxMessages = stats
    ? Math.max(stats.messages, stats.messages_today, 1)
    : 1;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Usage</h2>
          <p className="text-sm text-gray-500">Detailed usage statistics</p>
        </div>
        <button
          onClick={loadStats}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-nexus-border px-3 py-1.5 text-xs text-gray-400 transition-colors hover:bg-nexus-elevated hover:text-gray-200"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {!loading && summary && (
        <div className="mb-6 rounded-xl border border-nexus-border bg-nexus-surface p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-200">
              Verbrauch im aktuellen Monat ({summary.period})
            </h3>
            <span className="text-xs text-gray-500">
              Limit:{" "}
              {summary.default_token_limit?.toLocaleString() ?? "-"} Token /
              Monat
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <div className="rounded-lg bg-nexus-elevated/60 p-3">
              <p className="flex items-center gap-1 text-xs text-gray-500">
                <Zap size={12} className="text-blue-400" /> Gesamt-Tokens
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-100">
                {formatNumber(summary.total_tokens_used ?? 0)}
              </p>
            </div>
            <div className="rounded-lg bg-nexus-elevated/60 p-3">
              <p className="flex items-center gap-1 text-xs text-gray-500">
                <MessageSquare size={12} className="text-blue-400" />{" "}
                Chat-Tokens
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-100">
                {formatNumber(summary.total_chat_tokens ?? 0)}
              </p>
            </div>
            <div className="rounded-lg bg-nexus-elevated/60 p-3">
              <p className="flex items-center gap-1 text-xs text-gray-500">
                <ImageIcon size={12} className="text-purple-400" /> Bild-Tokens
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-100">
                {formatNumber(summary.total_image_tokens ?? 0)}
              </p>
            </div>
            <div className="rounded-lg bg-nexus-elevated/60 p-3">
              <p className="flex items-center gap-1 text-xs text-gray-500">
                <Activity size={12} className="text-gray-400" /> Chat-Aktionen
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-100">
                {formatNumber(summary.total_chat_actions ?? 0)}
              </p>
            </div>
            <div className="rounded-lg bg-nexus-elevated/60 p-3">
              <p className="flex items-center gap-1 text-xs text-gray-500">
                <ImageIcon size={12} className="text-purple-400" />{" "}
                Bild-Aktionen
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-100">
                {formatNumber(summary.total_image_actions ?? 0)}
              </p>
            </div>
          </div>
          <p className="mt-4 text-[11px] text-gray-500">
            Erfasst werden nur erfolgreich gebuchte Aktionen –
            fehlgeschlagene Bildgenerierungen werden im Backend automatisch
            erstattet und tauchen hier nicht auf.
          </p>
        </div>
      )}

      {loading && !stats ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : stats ? (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-nexus-border bg-nexus-surface p-4">
              <p className="text-xs text-gray-500">Tokens Today</p>
              <p className="mt-1 text-xl font-semibold text-gray-100">
                {formatNumber(stats.tokens_today)}
              </p>
            </div>
            <div className="rounded-xl border border-nexus-border bg-nexus-surface p-4">
              <p className="text-xs text-gray-500">Tokens Total</p>
              <p className="mt-1 text-xl font-semibold text-gray-100">
                {formatNumber(stats.total_tokens)}
              </p>
            </div>
            <div className="rounded-xl border border-nexus-border bg-nexus-surface p-4">
              <p className="text-xs text-gray-500">Messages Today</p>
              <p className="mt-1 text-xl font-semibold text-gray-100">
                {formatNumber(stats.messages_today)}
              </p>
            </div>
            <div className="rounded-xl border border-nexus-border bg-nexus-surface p-4">
              <p className="text-xs text-gray-500">Total Messages</p>
              <p className="mt-1 text-xl font-semibold text-gray-100">
                {formatNumber(stats.messages)}
              </p>
            </div>
          </div>

          {/* Bar charts */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Token usage */}
            <div className="rounded-xl border border-nexus-border bg-nexus-surface p-6">
              <h3 className="mb-4 text-sm font-medium text-gray-200">
                Token Usage
              </h3>
              <div className="space-y-4">
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-gray-400">Today</span>
                    <span className="text-gray-300">
                      {formatNumber(stats.tokens_today)}
                    </span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-nexus-elevated">
                    <div
                      className="h-full rounded-full bg-blue-500/60 transition-all"
                      style={{
                        width: `${(stats.tokens_today / maxTokens) * 100}%`,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-gray-400">Total</span>
                    <span className="text-gray-300">
                      {formatNumber(stats.total_tokens)}
                    </span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-nexus-elevated">
                    <div
                      className="h-full rounded-full bg-blue-500 transition-all"
                      style={{
                        width: `${(stats.total_tokens / maxTokens) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Message usage */}
            <div className="rounded-xl border border-nexus-border bg-nexus-surface p-6">
              <h3 className="mb-4 text-sm font-medium text-gray-200">
                Message Usage
              </h3>
              <div className="space-y-4">
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-gray-400">Today</span>
                    <span className="text-gray-300">
                      {formatNumber(stats.messages_today)}
                    </span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-nexus-elevated">
                    <div
                      className="h-full rounded-full bg-blue-500/60 transition-all"
                      style={{
                        width: `${
                          (stats.messages_today / maxMessages) * 100
                        }%`,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-gray-400">Total</span>
                    <span className="text-gray-300">
                      {formatNumber(stats.messages)}
                    </span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-nexus-elevated">
                    <div
                      className="h-full rounded-full bg-blue-500 transition-all"
                      style={{
                        width: `${
                          (stats.messages / maxMessages) * 100
                        }%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <p className="py-16 text-center text-sm text-gray-500">
          No usage data available
        </p>
      )}
    </div>
  );
}