import { useState, useEffect } from "react";
import {
  Users,
  MessageSquare,
  Zap,
  Activity,
  RefreshCw,
} from "lucide-react";
import { getDashboard } from "../../lib/api";
import type { DashboardStats } from "../../types";

export default function DashboardSection() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  async function loadStats() {
    setLoading(true);
    try {
      const data = await getDashboard();
      setStats(data);
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

  const cards = stats
    ? [
        {
          label: "Total Users",
          value: stats.users,
          icon: Users,
          color: "text-blue-500",
          bg: "bg-blue-500/10",
        },
        {
          label: "Active Users",
          value: stats.active_users,
          icon: Activity,
          color: "text-green-500",
          bg: "bg-green-500/10",
        },
        {
          label: "Total Chats",
          value: stats.chats,
          icon: MessageSquare,
          color: "text-blue-500",
          bg: "bg-blue-500/10",
        },
        {
          label: "Total Messages",
          value: stats.messages,
          icon: MessageSquare,
          color: "text-blue-500",
          bg: "bg-blue-500/10",
        },
        {
          label: "Tokens Today",
          value: stats.tokens_today,
          icon: Zap,
          color: "text-amber-500",
          bg: "bg-amber-500/10",
        },
      ]
    : [];

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Dashboard</h2>
          <p className="text-sm text-gray-500">System overview</p>
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

      {loading && !stats ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((card) => {
            const Icon = card.icon;
            return (
              <div
                key={card.label}
                className="rounded-xl border border-nexus-border bg-nexus-surface p-5"
              >
                <div className="mb-3 flex items-center gap-3">
                  <div
                    className={`flex h-9 w-9 items-center justify-center rounded-lg ${card.bg}`}
                  >
                    <Icon size={18} className={card.color} />
                  </div>
                  <span className="text-sm text-gray-400">{card.label}</span>
                </div>
                <p className="text-2xl font-semibold text-gray-100">
                  {formatNumber(card.value)}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}