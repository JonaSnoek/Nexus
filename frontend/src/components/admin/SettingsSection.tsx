import { useState, useEffect } from "react";
import { Save, AlertCircle, Check, KeyRound, Gauge, Loader2, Image as ImageIcon } from "lucide-react";
import {
  getSsoSettings,
  updateSsoSettings,
  getDefaultLimits,
  updateDefaultLimits,
  getImageProviderSettings,
  updateImageProviderSettings,
} from "../../lib/api";
import type { SsoSettings, DefaultLimits, ImageProviderSettings, ImageProviderSettingsUpdate } from "../../types";

const emptySso: SsoSettings = {
  oidc_enabled: false,
  oidc_issuer_url: "",
  oidc_client_id: "",
  oidc_client_secret: "",
  oidc_redirect_uri: "",
  oidc_group_admins: "admins",
  oidc_group_users: "users",
};

export default function SettingsSection() {
  const [sso, setSso] = useState<SsoSettings>(emptySso);
  const [limits, setLimits] = useState<DefaultLimits>({
    default_token_limit: 100,
    default_message_limit: 1000,
    chat_message_cost: 1,
    image_generation_cost: 10,
  });
  const [loading, setLoading] = useState(true);
  const [ssoSaving, setSsoSaving] = useState(false);
  const [limitsSaving, setLimitsSaving] = useState(false);
  const [imageSaving, setImageSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [image, setImage] = useState<ImageProviderSettings>({
    image_provider: "none",
    image_model: "",
    image_api_url: "",
    has_api_key: false,
    api_key_tail: "",
    configured: false,
  });
  const [newApiKey, setNewApiKey] = useState("");
  const [clearKey, setClearKey] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const [ssoData, limitsData, imageData] = await Promise.all([
        getSsoSettings(),
        getDefaultLimits(),
        getImageProviderSettings(),
      ]);
      setSso(ssoData);
      setLimits(limitsData);
      setImage(imageData);
      setNewApiKey("");
      setClearKey(false);
    } catch (err: any) {
      setError(err.message || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }

  function notify(msg: string) {
    setSuccess(msg);
    setTimeout(() => setSuccess(null), 3000);
  }

  async function handleSaveSso(e: React.FormEvent) {
    e.preventDefault();
    setSsoSaving(true);
    setError(null);
    try {
      const updated = await updateSsoSettings(sso);
      setSso(updated);
      notify("SSO settings saved");
    } catch (err: any) {
      setError(err.message || "Failed to save SSO settings");
    } finally {
      setSsoSaving(false);
    }
  }

  async function handleSaveLimits(e: React.FormEvent) {
    e.preventDefault();
    setLimitsSaving(true);
    setError(null);
    try {
      const updated = await updateDefaultLimits(limits);
      setLimits(updated);
      notify("Default limits saved");
    } catch (err: any) {
      setError(err.message || "Failed to save default limits");
    } finally {
      setLimitsSaving(false);
    }
  }

  async function handleSaveImage(e: React.FormEvent) {
    e.preventDefault();
    setImageSaving(true);
    setError(null);
    try {
      const payload: ImageProviderSettingsUpdate = {
        image_provider: image.image_provider,
        image_model: image.image_model,
        image_api_url: image.image_api_url,
      };
      if (clearKey) {
        payload.image_api_key = "";
      } else if (newApiKey.trim()) {
        payload.image_api_key = newApiKey.trim();
      }
      const updated = await updateImageProviderSettings(payload);
      setImage(updated);
      setNewApiKey("");
      setClearKey(false);
      notify("Image provider settings saved");
    } catch (err: any) {
      setError(err.message || "Failed to save image provider settings");
    } finally {
      setImageSaving(false);
    }
  }

  const inputClass =
    "w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50 disabled:opacity-40";

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-100">Settings</h2>
        <p className="text-sm text-gray-500">
          SSO / OIDC configuration and default limits for new users
        </p>
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

      <div className="space-y-6">
        {/* SSO / OIDC */}
        <form
          onSubmit={handleSaveSso}
          className="rounded-xl border border-nexus-border bg-nexus-surface p-6"
        >
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/10 text-blue-500">
              <KeyRound size={18} />
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-100">
                Single Sign-On (SSO / OIDC)
              </h3>
              <p className="text-xs text-gray-500">
                Compatible with Authentik, Keycloak and other OIDC providers.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                checked={sso.oidc_enabled}
                onChange={(e) =>
                  setSso((p) => ({ ...p, oidc_enabled: e.target.checked }))
                }
                className="h-4 w-4 rounded border-gray-600 bg-nexus-elevated"
              />
              Enable SSO login
            </label>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs text-gray-400">
                  Issuer URL
                </label>
                <input
                  type="url"
                  value={sso.oidc_issuer_url}
                  onChange={(e) =>
                    setSso((p) => ({ ...p, oidc_issuer_url: e.target.value }))
                  }
                  placeholder="https://auth.example.com/application/o/nexus/"
                  className={inputClass}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Client ID
                </label>
                <input
                  type="text"
                  value={sso.oidc_client_id}
                  onChange={(e) =>
                    setSso((p) => ({ ...p, oidc_client_id: e.target.value }))
                  }
                  className={inputClass}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Client Secret
                </label>
                <input
                  type="password"
                  value={sso.oidc_client_secret}
                  onChange={(e) =>
                    setSso((p) => ({
                      ...p,
                      oidc_client_secret: e.target.value,
                    }))
                  }
                  className={inputClass}
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs text-gray-400">
                  Redirect URI
                </label>
                <input
                  type="url"
                  value={sso.oidc_redirect_uri}
                  onChange={(e) =>
                    setSso((p) => ({ ...p, oidc_redirect_uri: e.target.value }))
                  }
                  placeholder="https://nexus.example.com/auth/callback"
                  className={inputClass}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Admin group
                </label>
                <input
                  type="text"
                  value={sso.oidc_group_admins}
                  onChange={(e) =>
                    setSso((p) => ({ ...p, oidc_group_admins: e.target.value }))
                  }
                  className={inputClass}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  User group
                </label>
                <input
                  type="text"
                  value={sso.oidc_group_users}
                  onChange={(e) =>
                    setSso((p) => ({ ...p, oidc_group_users: e.target.value }))
                  }
                  className={inputClass}
                />
              </div>
            </div>
          </div>

          <div className="mt-5 flex justify-end">
            <button
              type="submit"
              disabled={ssoSaving}
              className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50"
            >
              {ssoSaving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Save size={14} />
              )}
              Save SSO Settings
            </button>
          </div>
        </form>

        {/* Default limits */}
        <form
          onSubmit={handleSaveLimits}
          className="rounded-xl border border-nexus-border bg-nexus-surface p-6"
        >
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/10 text-blue-500">
              <Gauge size={18} />
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-100">
                Limits &amp; Verbrauch
              </h3>
              <p className="text-xs text-gray-500">
                Globale Standardwerte für neue Benutzer (Standard-Limit). Die
                Aktionskosten bestimmen, wie viele Token vom monatlichen
                Kontingent pro Aktion abgezogen werden. Limits gelten pro
                Kalendermonat.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Token limit / month (Standard)
              </label>
              <input
                type="number"
                min={0}
                value={limits.default_token_limit}
                onChange={(e) =>
                  setLimits((p) => ({
                    ...p,
                    default_token_limit: Number(e.target.value),
                  }))
                }
                className={inputClass}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Message limit / month
              </label>
              <input
                type="number"
                min={0}
                value={limits.default_message_limit}
                onChange={(e) =>
                  setLimits((p) => ({
                    ...p,
                    default_message_limit: Number(e.target.value),
                  }))
                }
                className={inputClass}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Token-Verbrauch pro Chat-Nachricht
              </label>
              <input
                type="number"
                min={0}
                step={1}
                value={limits.chat_message_cost}
                onChange={(e) =>
                  setLimits((p) => ({
                    ...p,
                    chat_message_cost: Number(e.target.value),
                  }))
                }
                className={inputClass}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Token-Verbrauch pro Bildgenerierung
              </label>
              <input
                type="number"
                min={0}
                step={1}
                value={limits.image_generation_cost}
                onChange={(e) =>
                  setLimits((p) => ({
                    ...p,
                    image_generation_cost: Number(e.target.value),
                  }))
                }
                className={inputClass}
              />
            </div>
          </div>

          <p className="mt-3 text-[11px] text-gray-500">
            Beispiel: bei 100 Tokens Kontingent und 1 Token pro Nachricht sind
            100 Nachrichten im Monat möglich; eine Bildgenerierung kostet
            standardmäßig 10 Tokens.
          </p>

          <div className="mt-5 flex justify-end">
            <button
              type="submit"
              disabled={limitsSaving}
              className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50"
            >
              {limitsSaving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Save size={14} />
              )}
              Save Default Limits
            </button>
          </div>
        </form>

        {/* Image generation provider */}
        <form
          onSubmit={handleSaveImage}
          className="rounded-xl border border-nexus-border bg-nexus-surface p-6"
        >
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400">
              <ImageIcon size={18} />
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-100">
                Bildgenerierung (Provider)
              </h3>
              <p className="text-xs text-gray-500">
                Konfiguriert den Bildprovider für die Image-Generierung.
                Getestet mit OpenAI-kompatiblen APIs (z. B. DALL-E, selbst
                gehostete Backends). Der API-Key wird nie an das Frontend
                ausgegeben.
              </p>
            </div>
            <div className="ml-auto">
              {image.configured ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-[11px] font-medium text-green-400">
                  <Check size={12} /> Konfiguriert
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-yellow-500/10 px-2 py-0.5 text-[11px] font-medium text-yellow-300">
                  <AlertCircle size={12} /> Nicht konfiguriert
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Provider
              </label>
              <select
                value={image.image_provider}
                onChange={(e) =>
                  setImage((p) => ({
                    ...p,
                    image_provider: e.target.value,
                  }))
                }
                className={inputClass}
              >
                <option value="none">Keiner (deaktiviert)</option>
                <option value="openai_compatible">
                  OpenAI-kompatibel (z. B. DALL-E)
                </option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">
                Modell
              </label>
              <input
                type="text"
                value={image.image_model}
                onChange={(e) =>
                  setImage((p) => ({ ...p, image_model: e.target.value }))
                }
                placeholder="dall-e-3"
                className={inputClass}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs text-gray-400">
                API-URL (Basis, z. B. https://api.openai.com/v1)
              </label>
              <input
                type="url"
                value={image.image_api_url}
                onChange={(e) =>
                  setImage((p) => ({ ...p, image_api_url: e.target.value }))
                }
                placeholder="https://api.openai.com/v1"
                className={inputClass}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs text-gray-400">
                API-Key {image.has_api_key && "(aktuell hinterlegt …" + image.api_key_tail + ")"}
              </label>
              <input
                type="password"
                value={newApiKey}
                disabled={clearKey}
                onChange={(e) => setNewApiKey(e.target.value)}
                placeholder={
                  image.has_api_key
                    ? "Neuen Key eingeben, um den bestehenden zu ersetzen (leer = behalten)"
                    : "API-Key eingeben"
                }
                className={inputClass}
              />
              {image.has_api_key && !clearKey && (
                <label className="mt-2 flex items-center gap-2 text-xs text-gray-400">
                  <input
                    type="checkbox"
                    checked={clearKey}
                    onChange={(e) => setClearKey(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-600 bg-nexus-elevated"
                  />
                  Bestehenden API-Key löschen
                </label>
              )}
            </div>
          </div>

          <div className="mt-5 flex justify-end">
            <button
              type="submit"
              disabled={imageSaving}
              className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50"
            >
              {imageSaving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Save size={14} />
              )}
              Save Image Provider
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}