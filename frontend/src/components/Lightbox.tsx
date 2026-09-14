import { Download, X } from "lucide-react";
import type { GeneratedImage } from "../types";
import { formatSeconds } from "./ChatImage";

interface LightboxProps {
  image: GeneratedImage;
  url: string;
  onClose: () => void;
}

export default function Lightbox({ image, url, onClose }: LightboxProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative max-h-full max-w-5xl"
        onClick={(e) => e.stopPropagation()}
      >
        <img
          src={url}
          alt={image.prompt}
          className="max-h-[85vh] w-auto rounded-xl"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-300">
          <div className="min-w-0">
            <p className="truncate">{image.prompt}</p>
            <p className="text-xs text-gray-500">
              {image.model}
              {image.seconds != null && ` · ${formatSeconds(image.seconds)}`}
              {image.width && image.height && ` · ${image.width}×${image.height}`}
              {image.bytes_size != null &&
                ` · ${(image.bytes_size / 1024).toFixed(0)} KB`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={url}
              download={`nexus-image-${image.id}.png`}
              className="flex items-center gap-1 rounded-lg bg-blue-500 px-3 py-1.5 text-white transition-colors hover:bg-blue-600"
            >
              <Download size={14} /> Herunterladen
            </a>
            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-white transition-colors hover:bg-white/20"
              title="Schließen"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}