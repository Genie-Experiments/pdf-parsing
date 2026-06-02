"use client";

import { useEffect, useRef, useState } from "react";
import { FileText, X, Loader2, AlertTriangle } from "lucide-react";
import { UserQuota } from "@/lib/api";

export interface JobConfig {
  file: File;
  page?: number;
  segmentsToRefine: string[];
}

const ALL_SEGMENTS = [
  { id: "tab",  label: "Tables",      available: true  },
  { id: "code", label: "Code blocks", available: false },
  { id: "fig",  label: "Figures",     available: false },
];

interface Props {
  file: File;
  onSubmit: (config: JobConfig) => void;
  onCancel: () => void;
  disabled?: boolean;
  quota?: UserQuota;
  onTotalPages?: (n: number | null) => void;
  onQuotaExceeded?: (exceeded: boolean) => void;
}

let pdfjs: typeof import("pdfjs-dist") | null = null;
async function getPdfJs() {
  if (!pdfjs) {
    pdfjs = await import("pdfjs-dist");
    pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  }
  return pdfjs;
}

export function JobOptions({ file, onSubmit, onCancel, disabled, quota, onTotalPages, onQuotaExceeded }: Props) {
  const [pageMode, setPageMode] = useState<"all" | "single">("all");
  const [pageNum, setPageNum] = useState("1");
  const [segments, setSegments] = useState<Set<string>>(new Set(["tab"]));

  function toggleSegment(id: string) {
    setSegments(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const pdfDocRef = useRef<any>(null);
  const [docReady, setDocReady] = useState(false);
  const [totalPages, setTotalPages] = useState<number | null>(null);

  const [thumbnail, setThumbnail] = useState<string | null>(null);
  const [thumbLoading, setThumbLoading] = useState(false);
  const [thumbError, setThumbError] = useState<string | null>(null);

  // Load PDF document once when file is set
  useEffect(() => {
    let cancelled = false;
    let url: string | null = null;
    setDocReady(false);
    pdfDocRef.current = null;

    (async () => {
      try {
        const lib = await getPdfJs();
        url = URL.createObjectURL(file);
        const doc = await lib.getDocument(url).promise;
        if (cancelled) return;
        pdfDocRef.current = doc;
        setTotalPages(doc.numPages);
        onTotalPages?.(doc.numPages);
        setDocReady(true);
      } catch {
        // non-fatal — thumbnail just won't appear
      }
    })();

    return () => {
      cancelled = true;
      pdfDocRef.current = null;
      if (url) URL.revokeObjectURL(url);
      onTotalPages?.(null);
    };
  }, [file]); // eslint-disable-line react-hooks/exhaustive-deps

  // Render thumbnail whenever page number or doc readiness changes (debounced)
  useEffect(() => {
    if (pageMode !== "single") {
      setThumbnail(null);
      setThumbError(null);
      return;
    }

    const pageN = parseInt(pageNum, 10);
    if (isNaN(pageN) || pageN < 1) return;

    setThumbLoading(true);
    setThumbError(null);

    const timer = setTimeout(async () => {
      const doc = pdfDocRef.current;
      if (!doc) {
        setThumbLoading(false);
        return;
      }

      if (pageN > doc.numPages) {
        setThumbError(`PDF only has ${doc.numPages} pages`);
        setThumbLoading(false);
        return;
      }

      try {
        const page = await doc.getPage(pageN);
        const vp = page.getViewport({ scale: 1 });
        const scale = 168 / vp.width;
        const scaled = page.getViewport({ scale });

        const canvas = document.createElement("canvas");
        canvas.width = scaled.width;
        canvas.height = scaled.height;
        await page.render({ canvasContext: canvas.getContext("2d")!, viewport: scaled }).promise;

        setThumbnail(canvas.toDataURL());
        setThumbError(null);
      } catch {
        setThumbError("Could not render page");
      }
      setThumbLoading(false);
    }, 400);

    return () => clearTimeout(timer);
  }, [pageMode, pageNum, docReady]);

  const quotaExceeded =
    pageMode === "all" &&
    totalPages !== null &&
    quota !== undefined &&
    !quota.bypassed &&
    totalPages > quota.pages_remaining;

  useEffect(() => {
    onQuotaExceeded?.(quotaExceeded);
  }, [quotaExceeded]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit() {
    if (quotaExceeded) return;
    const page = pageMode === "single" ? parseInt(pageNum, 10) : undefined;
    onSubmit({ file, page, segmentsToRefine: [...segments] });
  }

  const sizeKb = (file.size / 1024).toFixed(0);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-5 shadow-sm">
      {/* File info */}
      <div className="flex items-start gap-3">
        <FileText className="w-5 h-5 text-indigo-500 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate">{file.name}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {sizeKb} KB{totalPages ? ` · ${totalPages} pages` : ""}
          </p>
        </div>
        <button
          onClick={onCancel}
          className="p-1 rounded hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600"
          aria-label="Remove file"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Page selection */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Pages</p>
        <div className="flex gap-4 items-start">
          {/* Controls (left) */}
          <div className="flex-1 space-y-3">
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="radio"
                  name="pageMode"
                  checked={pageMode === "all"}
                  onChange={() => setPageMode("all")}
                  className="accent-indigo-500"
                />
                <span className="text-sm text-gray-700">Entire document</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="radio"
                  name="pageMode"
                  checked={pageMode === "single"}
                  onChange={() => setPageMode("single")}
                  className="accent-indigo-500"
                />
                <span className="text-sm text-gray-700">Single page</span>
              </label>
              {pageMode === "single" && (
                <input
                  type="number"
                  min={1}
                  max={totalPages ?? undefined}
                  value={pageNum}
                  onChange={(e) => setPageNum(e.target.value)}
                  placeholder="Page #"
                  className="w-20 text-sm px-2.5 py-1 rounded-lg bg-white border border-gray-300 text-gray-800 focus:outline-none focus:border-indigo-500 transition-colors"
                />
              )}
            </div>
          </div>

          {/* Thumbnail (right) */}
          {pageMode === "single" && (
            <div className="shrink-0">
              {thumbLoading && (
                <div className="w-[120px] h-[160px] rounded-lg border border-gray-200 bg-gray-50 flex items-center justify-center">
                  <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />
                </div>
              )}
              {!thumbLoading && thumbError && (
                <p className="flex items-start gap-1.5 text-xs text-red-500">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{thumbError}</span>
                </p>
              )}
              {!thumbLoading && thumbnail && !thumbError && (
                <div className="rounded-lg border border-gray-200 overflow-hidden shadow-sm">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={thumbnail}
                    alt={`Page ${pageNum} preview`}
                    className="block"
                    style={{ width: 120 }}
                  />
                  <p className="text-center text-[10px] text-gray-400 py-1.5 bg-gray-50 border-t border-gray-100">
                    Page {pageNum}{totalPages ? ` of ${totalPages}` : ""}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Segments to refine */}
      <div className="space-y-2.5">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Refine segments
        </p>
        <div className="flex flex-wrap gap-4">
          {ALL_SEGMENTS.map(({ id, label, available }) => (
            <label
              key={id}
              className={[
                "flex items-center gap-2 select-none",
                available ? "cursor-pointer" : "cursor-not-allowed opacity-40",
              ].join(" ")}
            >
              <input
                type="checkbox"
                disabled={!available}
                checked={available && segments.has(id)}
                onChange={() => available && toggleSegment(id)}
                className="w-3.5 h-3.5"
              />
              <span className="text-sm text-gray-700">{label}</span>
              {!available && (
                <span className="text-[10px] bg-gray-100 text-gray-400 px-1 py-0.5 rounded font-medium leading-none">
                  soon
                </span>
              )}
            </label>
          ))}
        </div>
        <p className="text-xs text-gray-400">
          Selected segments will be post-processed for accuracy.
        </p>
      </div>

      {/* Buttons */}
      <div className="flex gap-3 pt-1">
        <button
          onClick={onCancel}
          disabled={disabled}
          className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-500 hover:text-gray-700 hover:border-gray-400 transition-colors disabled:opacity-40"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={disabled || quotaExceeded}
          className="flex-1 px-4 py-2 text-sm font-medium rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 transition-colors"
        >
          Start Processing →
        </button>
      </div>

    </div>
  );
}
