import { useState, useEffect } from "react";
import { ScrollText, RefreshCw, Filter } from "lucide-react";
import { getLogs } from "../../lib/api";
import type { AuditLog } from "../../types";

export default function LogsSection() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    loadLogs();
  }, [actionFilter, limit]);

  async function loadLogs() {
    setLoading(true);
    try {
      const data = await getLogs({
        action: actionFilter || undefined,
        limit,
      });
      setLogs(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  function getActionBadge(action: string) {
    const colors: Record<string, string> = {
      login: "bg-green-500/10 text-green-400",
      logout: "bg-gray-500/10 text-gray-400",
      user_created: "bg-blue-500/10 text-blue-400",
      chat_deleted: "bg-red-500/10 text-red-400",
      setup_completed: "bg-blue-500/10 text-blue-400",
      oidc_login: "bg-green-500/10 text-green-400",
      user_updated: "bg-yellow-500/10 text-yellow-400",
      user_deactivated: "bg-red-500/10 text-red-400",
      permissions_updated: "bg-yellow-500/10 text-yellow-400",
      limits_updated: "bg-yellow-500/10 text-yellow-400",
    };

    const colorClass =
      colors[action] || "bg-gray-500/10 text-gray-400";

    return (
      <span
        className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${colorClass}`}
      >
        {action}
      </span>
    );
  }

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Audit Logs</h2>
          <p className="text-sm text-gray-500">System activity log</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-lg border border-nexus-border px-2 py-1">
            <Filter size={12} className="text-gray-500" />
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="bg-transparent text-xs text-gray-300 outline-none"
            >
              <option value="">All actions</option>
              <option value="login">Login</option>
              <option value="oidc_login">OIDC Login</option>
              <option value="user_created">User Created</option>
              <option value="user_updated">User Updated</option>
              <option value="user_deactivated">User Deactivated</option>
              <option value="chat_deleted">Chat Deleted</option>
            </select>
          </div>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="rounded-lg border border-nexus-border bg-nexus-surface px-2 py-1 text-xs text-gray-300 outline-none"
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
          </select>
          <button
            onClick={loadLogs}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-nexus-border px-3 py-1.5 text-xs text-gray-400 transition-colors hover:bg-nexus-elevated hover:text-gray-200"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : logs.length === 0 ? (
        <div className="rounded-xl border border-nexus-border bg-nexus-surface p-8 text-center">
          <ScrollText size={32} className="mx-auto mb-3 text-gray-600" />
          <p className="text-sm text-gray-400">No audit logs found</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-nexus-border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-nexus-border bg-nexus-surface">
                <th className="px-4 py-3 text-xs font-medium text-gray-400">
                  Time
                </th>
                <th className="px-4 py-3 text-xs font-medium text-gray-400">
                  User
                </th>
                <th className="px-4 py-3 text-xs font-medium text-gray-400">
                  Action
                </th>
                <th className="hidden px-4 py-3 font-medium text-gray-400 lg:table-cell">
                  IP Address
                </th>
                <th className="hidden px-4 py-3 text-xs font-medium text-gray-400 md:table-cell">
                  Details
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-nexus-border">
              {logs.map((log) => (
                <tr
                  key={log.id}
                  className="transition-colors hover:bg-nexus-elevated/50"
                >
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-gray-500">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-200">
                    {log.username || "-"}
                  </td>
                  <td className="px-4 py-3">{getActionBadge(log.action)}</td>
                  <td className="hidden px-4 py-3 font-mono text-xs text-gray-500 lg:table-cell">
                    {log.ip_address || "-"}
                  </td>
                  <td className="hidden max-w-xs truncate px-4 py-3 text-xs text-gray-500 md:table-cell">
                    {log.details || "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}