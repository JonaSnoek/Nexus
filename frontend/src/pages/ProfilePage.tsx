import { useState, useEffect } from "react";
import Layout from "../components/Layout";
import { useAuth } from "../contexts/AuthContext";
import { getMyUsage } from "../lib/api";
import type { Usage } from "../types";
import { User, MessageSquare, Zap, Activity } from "lucide-react";

export default function ProfilePage() {
  const { user } = useAuth();
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getMyUsage();
        setUsage(data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function formatNumber(n: number): string {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(1) + "K";
    return n.toString();
  }

  function getTokenPercent(): number {
    if (!usage || !usage.token_limit || usage.token_limit <= 0) return 0;
    return Math.min(100, (usage.tokens_used / usage.token_limit) * 100);
  }

  function getMessagePercent(): number {
    if (!usage || !usage.message_limit || usage.message_limit <= 0) return 0;
    return Math.min(100, (usage.messages_used / usage.message_limit) * 100);
  }

  const tokenLimitLabel =
    user?.unlimited != null && user.unlimited
      ? "∞ Unbegrenzt"
      : formatNumber((user?.effective_token_limit ?? user?.monthly_token_limit) || 0);
  const tokensRemainingLabel =
    user?.unlimited != null && user.unlimited
      ? "∞ Unbegrenzt"
      : formatNumber((user?.tokens_remaining ?? user?.tokens_remaining_month) || 0);

  return (
    <Layout>
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 py-8">
          <h1 className="mb-6 text-xl font-semibold text-gray-100">Profile</h1>

          {/* User info */}
          <div className="mb-6 rounded-xl border border-nexus-border bg-nexus-surface p-6">
            <div className="mb-4 flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-blue-500/10 text-blue-500">
                <User size={24} />
              </div>
              <div>
                <h2 className="text-lg font-medium text-gray-100">
                  {user?.display_name || user?.username}
                </h2>
                <p className="text-sm text-gray-500">@{user?.username}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 border-t border-nexus-border pt-4">
              <div>
                <p className="text-xs text-gray-500">Email</p>
                <p className="text-sm text-gray-300">{user?.email || "-"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Role</p>
                <p className="text-sm capitalize text-gray-300">{user?.role}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Token Limit (monthly)</p>
                <p className="text-sm text-gray-300">{tokenLimitLabel}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Message Limit (monthly)</p>
                <p className="text-sm text-gray-300">
                  {formatNumber(user?.monthly_message_limit || 0)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Tokens remaining</p>
                <p className="text-sm font-medium text-gray-300">
                  {tokensRemainingLabel}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Messages remaining</p>
                <p className="text-sm font-medium text-gray-300">
                  {formatNumber(user?.messages_remaining_month || 0)}
                </p>
              </div>
            </div>
          </div>

          {/* Usage stats */}
          <div className="rounded-xl border border-nexus-border bg-nexus-surface p-6">
            <h3 className="mb-1 text-sm font-medium text-gray-200">
              This Month&apos;s Usage
            </h3>
            <p className="mb-4 text-xs text-gray-500">
              Period: {usage?.period || user?.period || "-"}
            </p>

            {loading ? (
              <div className="flex justify-center py-8">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
              </div>
            ) : usage ? (
              <div className="space-y-5">
                {/* Token usage */}
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-gray-300">
                      <Zap size={14} className="text-blue-500" />
                      Tokens
                    </div>
                    {usage.token_limit === -1 ? (
                      <span className="text-xs text-emerald-400">
                        ∞ Unbegrenzt · {formatNumber(usage.tokens_used)} verbraucht
                      </span>
                    ) : (
                      <span className="text-xs text-gray-500">
                        {formatNumber(usage.tokens_used)} /{" "}
                        {formatNumber(usage.token_limit || 0)}
                      </span>
                    )}
                  </div>
                  {usage.token_limit !== -1 && (
                    <div className="h-2 overflow-hidden rounded-full bg-nexus-elevated">
                      <div
                        className="h-full rounded-full bg-blue-500 transition-all"
                        style={{ width: `${getTokenPercent()}%` }}
                      />
                    </div>
                  )}
                </div>

                {/* Message usage */}
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-gray-300">
                      <MessageSquare size={14} className="text-blue-500" />
                      Messages
                    </div>
                    <span className="text-xs text-gray-500">
                      {usage.messages_used} / {usage.message_limit || 0}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-nexus-elevated">
                    <div
                      className="h-full rounded-full bg-blue-500 transition-all"
                      style={{ width: `${getMessagePercent()}%` }}
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2 border-t border-nexus-border pt-4 text-xs text-gray-500">
                  <Activity size={14} />
                  Period: {usage?.period || "-"}
                </div>
              </div>
            ) : (
              <p className="text-center text-sm text-gray-500">
                No usage data available
              </p>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}