import { useState, useEffect } from "react";
import { Cpu, Download, RefreshCw, AlertCircle, Check } from "lucide-react";
import { getModels, pullModel } from "../../lib/api";
import type { ModelInfo } from "../../types";

export default function ModelsSection() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [pulling, setPulling] = useState(false);
  const [pullInput, setPullInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadModels();
  }, []);

  async function loadModels() {
    setLoading(true);
    try {
      const data = await getModels();
      setModels(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  async function handlePull(e: React.FormEvent) {
    e.preventDefault();
    if (!pullInput.trim() || pulling) return;
    setPulling(true);
    setError(null);
    setSuccess(null);

    try {
      await pullModel(pullInput.trim());
      setSuccess(`Model "${pullInput.trim()}" pulled successfully`);
      setPullInput("");
      await loadModels();
    } catch (err: any) {
      setError(err.message || "Failed to pull model");
    } finally {
      setPulling(false);
    }
  }

  function formatSize(bytes: number): string {
    if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + " GB";
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
    return bytes + " B";
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Models</h2>
          <p className="text-sm text-gray-500">
            Manage Ollama models
          </p>
        </div>
        <button
          onClick={loadModels}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-nexus-border px-3 py-1.5 text-xs text-gray-400 transition-colors hover:bg-nexus-elevated hover:text-gray-200"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-400">
          <AlertCircle size={14} className="shrink-0" />
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-500/20 bg-green-500/5 px-3 py-2 text-sm text-green-400">
          <Check size={14} className="shrink-0" />
          {success}
        </div>
      )}

      {/* Pull model */}
      <div className="mb-6 rounded-xl border border-nexus-border bg-nexus-surface p-4">
        <h3 className="mb-3 text-sm font-medium text-gray-200">
          Pull a Model
        </h3>
        <form onSubmit={handlePull} className="flex gap-2">
          <input
            type="text"
            value={pullInput}
            onChange={(e) => setPullInput(e.target.value)}
            placeholder="e.g. llama3, mistral, codellama"
            className="flex-1 rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-blue-500/50"
          />
          <button
            type="submit"
            disabled={pulling || !pullInput.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50"
          >
            {pulling ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <>
                <Download size={14} />
                Pull
              </>
            )}
          </button>
        </form>
      </div>

      {/* Model list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : models.length === 0 ? (
        <div className="rounded-xl border border-nexus-border bg-nexus-surface p-8 text-center">
          <Cpu size={32} className="mx-auto mb-3 text-gray-600" />
          <p className="text-sm text-gray-400">
            No models installed. Pull a model to get started.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {models.map((model) => (
            <div
              key={model.name}
              className="flex items-center justify-between rounded-xl border border-nexus-border bg-nexus-surface px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/10">
                  <Cpu size={16} className="text-blue-500" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-200">
                    {model.name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {model.size ? formatSize(model.size) : "Unknown size"}
                    {model.modified_at &&
                      ` - Modified ${new Date(model.modified_at).toLocaleDateString()}`}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
