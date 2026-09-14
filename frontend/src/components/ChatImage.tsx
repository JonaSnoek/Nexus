import { useEffect, useState } from "react";
import { Loader2, ImageOff, ExternalLink, Clock } from "lucide-react";
import type { GeneratedImage } from "../types";
import { getImageFileUrl } from "../lib/api";
import Lightbox from "./Lightbox";

export function formatSeconds(seconds: number | null): string {
  if (seconds == null) return "";
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const m = Math.floor(seconds / 60);
  return `${m} min ${Math.round(seconds % 60)} s`;
}

interface ChatImageProps {
  image: GeneratedImage;
}

export default function ChatImage({ image }: ChatImageProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  useEffect(() => {
    let active = true;
    if (image.status !== "done") return;
    getImageFileUrl(image.url)
      .then((u) => active && setUrl(u))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, [image.url, image.status]);

  if (image.status === "failed") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-400">
        <ImageOff size={14} className="shrink-0" />
        <span>
          Generierung fehlgeschlagen: {image.error || "unbekannter Fehler"}
        </span>
      </div>
    );
  }

  if (failed) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-3 py-2 text-sm text-yellow-300">
        <ImageOff size={14} className="shrink-0" />
        <span>Das Bild konnte nicht geladen werden.</span>
      </div>
    );
  }

  return (
    <div className="mt-2">
      {!url ? (
        <div className="flex items-center gap-2 rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-400">
          <Loader2 size={14} className="animate-spin" />
          <span>Bild wird geladen…</span>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setLightboxOpen(true)}
          className="group relative block overflow-hidden rounded-lg border border-nexus-border focus:outline-none"
          title="Zum Vergrößern klicken"
        >
          <img
            src={url}
            alt={image.prompt}
            className="max-h-96 w-auto max-w-full rounded-lg"
          />
          <span className="pointer-events-none absolute inset-0 flex items-end justify-center bg-gradient-to-t from-black/60 to-transparent p-2 opacity-0 transition-opacity group-hover:opacity-100">
            <span className="flex items-center gap-1 text-xs text-white">
              <ExternalLink size={12} /> Klicken zum Vergrößern
            </span>
          </span>
        </button>
      )}

      {(image.seconds != null || image.model || image.width) && (
        <div className="mt-1 flex items-center gap-3 text-[11px] text-gray-500">
          {image.seconds != null && (
            <span className="flex items-center gap-1">
              <Clock size={11} /> {formatSeconds(image.seconds)}
            </span>
          )}
          {image.model && <span>{image.model}</span>}
          {image.width && image.height && (
            <span>
              {image.width}×{image.height}
            </span>
          )}
        </div>
      )}

      {lightboxOpen && url && (
        <Lightbox
          image={image}
          url={url}
          onClose={() => setLightboxOpen(false)}
        />
      )}
    </div>
  );
}