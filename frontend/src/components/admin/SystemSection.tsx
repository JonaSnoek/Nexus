import { useState, useEffect } from "react";
import { Server, Cpu, HardDrive, RefreshCw } from "lucide-react";
import { getSystemInfo, getModelStatus, checkHealth } from "../../lib/api";
import type { SystemInfo } from "../../types";

export default function SystemSection() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [ollamaStatus, setOllamaStatus] = useState<string>("Unknown");
  const [defaultModel, setDefaultModel] = useState<string>("");
  const [defaultModelPresent, setDefaultModelPresent] = useState(false);
  const [dbStatus, setDbStatus] = useState<string>("ok");

  useEffect(() => {
    loadInfo();
  }, []);

  async function loadInfo() {
    setLoading(true);
    try {
      const [infoData, modelStatus, health] = await Promise.all([
        getSystemInfo(),
        getModelStatus().catch(() => null),
        checkHealth(),
      ]);
      setInfo(infoData);
      if (modelStatus) {
        setOllamaStatus(modelStatus.ollama);
        setDefaultModel(modelStatus.default_model);
        setDefaultModelPresent(modelStatus.default_model_present);
      }
      setDbStatus(health.database);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  function formatBytes(bytes: number | null | undefined): string {
    if (!bytes) return "-";
    if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + " GB";
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
    return bytes + " B";
  }

  function getStatusColor(status: string): string {
    switch (status?.toLowerCase()) {
      case "running":
      case "ok":
      case "healthy":
        return "text-green-400";
      case "stopped":
      case "error":
      case "unhealthy":
        return "text-red-400";
      default:
        return "text-yellow-400";
    }
  }

  const cpuPercent = info?.cpu_percent || 0;
  const memPercent = info?.memory_percent || 0;
  const diskPercent = info?.disk_percent || 0;

  function formatUptime(seconds: number | null | undefined): string {
    if (!seconds) return "-";
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (days > 0) return `${days}d ${hours}h ${mins}m`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">System</h2>
          <p className="text-sm text-gray-500">
            System health and resource usage
          </p>
        </div>
        <button
          onClick={loadInfo}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-nexus-border px-3 py-1.5 text-xs text-gray-400 transition-colors hover:bg-nexus-elevated hover:text-gray-200"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {loading && !info ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Resource bars */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {/* CPU */}
            <div className="rounded-xl border border-nexus-border bg-nexus-surface p-5">
              <div className="mb-3 flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
                  <Cpu size={16} className="text-blue-500" />
                </div>
                <span className="text-sm text-gray-300">CPU Load</span>
              </div>
              <p className="mb-2 text-2xl font-semibold text-gray-100">
                {cpuPercent.toFixed(1)}%
              </p>
              <div className="h-2 overflow-hidden rounded-full bg-nexus-elevated">
                <div
                  className={`h-full rounded-full transition-all ${
                    cpuPercent > 90
                      ? "bg-red-500"
                      : cpuPercent > 70
                      ? "bg-yellow-500"
                      : "bg-blue-500"
                  }`}
                  style={{ width: `${Math.min(100, cpuPercent)}%` }}
                />
              </div>
            </div>

            {/* Memory */}
            <div className="rounded-xl border border-nexus-border bg-nexus-surface p-5">
              <div className="mb-3 flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
                  <Server size={16} className="text-blue-500" />
                </div>
                <span className="text-sm text-gray-300">Memory</span>
              </div>
              <p className="mb-1 text-2xl font-semibold text-gray-100">
                {memPercent.toFixed(1)}%
              </p>
              <p className="mb-2 text-xs text-gray-500">
                {formatBytes(info?.memory_used)} /{" "}
                {formatBytes(info?.memory_total)}
              </p>
              <div className="h-2 overflow-hidden rounded-full bg-nexus-elevated">
                <div
                  className={`h-full rounded-full transition-all ${
                    memPercent > 90
                      ? "bg-red-500"
                      : memPercent > 70
                      ? "bg-yellow-500"
                      : "bg-blue-500"
                  }`}
                  style={{ width: `${Math.min(100, memPercent)}%` }}
                />
              </div>
            </div>

            {/* Disk */}
            <div className="rounded-xl border border-nexus-border bg-nexus-surface p-5">
              <div className="mb-3 flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
                  <HardDrive size={16} className="text-blue-500" />
                </div>
                <span className="text-sm text-gray-300">Disk</span>
              </div>
              <p className="mb-1 text-2xl font-semibold text-gray-100">
                {diskPercent.toFixed(1)}%
              </p>
              <p className="mb-2 text-xs text-gray-500">
                {formatBytes(info?.disk_used)} /{" "}
                {formatBytes(info?.disk_total)}
              </p>
              <div className="h-2 overflow-hidden rounded-full bg-nexus-elevated">
                <div
                  className={`h-full rounded-full transition-all ${
                    diskPercent > 90
                      ? "bg-red-500"
                      : diskPercent > 70
                      ? "bg-yellow-500"
                      : "bg-blue-500"
                  }`}
                  style={{ width: `${Math.min(100, diskPercent)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Service status */}
          <div className="rounded-xl border border-nexus-border bg-nexus-surface p-5">
            <h3 className="mb-4 text-sm font-medium text-gray-200">
              Service Status
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">NEXUS API</span>
                <span className="text-xs text-green-400">Running</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Database</span>
                <span className={`text-xs ${getStatusColor(dbStatus)}`}>
                  {dbStatus === "ok" ? "OK" : dbStatus}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Ollama</span>
                <span className={`text-xs ${getStatusColor(ollamaStatus)}`}>
                  {ollamaStatus}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">
                  Default Model ({defaultModel || "-"})
                </span>
                <span
                  className={`text-xs ${
                    defaultModelPresent ? "text-green-400" : "text-yellow-400"
                  }`}
                >
                  {defaultModel ? (defaultModelPresent ? "Installed" : "Not installed") : "Not configured"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Uptime</span>
                <span className="text-xs text-gray-400">
                  {formatUptime(info?.uptime)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}