"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useViewerStore } from "@/lib/store";

// pdfjs loaded lazily to avoid SSR issues
let pdfjs: typeof import("pdfjs-dist") | null = null;

async function getPdfJs() {
  if (!pdfjs) {
    pdfjs = await import("pdfjs-dist");
    // Use local worker copy (copied by next.config.ts)
    pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  }
  return pdfjs;
}

interface Props {
  pdfUrl: string;
  /** If set, viewer locks to this 0-indexed page and hides navigation. */
  lockedPage?: number;
}

export function PdfViewer({ pdfUrl, lockedPage }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [docLoaded, setDocLoaded] = useState(0);
  const pdfDocRef = useRef<any>(null);
  const renderTaskRef = useRef<any>(null);

  const { currentPage, setCurrentPage } = useViewerStore();

  // Load document once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const lib = await getPdfJs();
      const doc = await lib.getDocument(pdfUrl).promise;
      if (cancelled) return;
      pdfDocRef.current = doc;
      setTotalPages(doc.numPages);
      setCurrentPage(lockedPage ?? 0);
      setDocLoaded((n) => n + 1); // trigger render even if currentPage was already 0
    })();
    return () => {
      cancelled = true;
    };
  }, [pdfUrl, lockedPage, setCurrentPage]);

  // Render page whenever currentPage or docLoaded changes
  useEffect(() => {
    if (!pdfDocRef.current || !canvasRef.current) return;

    let cancelled = false;
    (async () => {
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }

      const page = await pdfDocRef.current.getPage(currentPage + 1); // pdfjs is 1-based
      if (cancelled) return;

      const container = containerRef.current;
      const containerWidth = container?.clientWidth ?? 800;
      const viewport = page.getViewport({ scale: 1 });
      const scale = containerWidth / viewport.width;
      const scaled = page.getViewport({ scale });

      const canvas = canvasRef.current!;
      const ctx = canvas.getContext("2d")!;
      canvas.width = scaled.width;
      canvas.height = scaled.height;

      const task = page.render({ canvasContext: ctx, viewport: scaled });
      renderTaskRef.current = task;
      try {
        await task.promise;
      } catch {
        // cancelled — ignore
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [currentPage, docLoaded]);

  return (
    <div className="flex flex-col h-full gap-2 p-2">
      {/* Canvas */}
      <div
        ref={containerRef}
        className="relative overflow-auto flex-1 bg-gray-50 rounded-lg border border-gray-200"
      >
        <canvas ref={canvasRef} className="block" />
      </div>

      {/* Page controls */}
      <div className="flex items-center justify-between px-2 py-1 bg-gray-100 rounded-lg text-sm text-gray-600 border border-gray-200 shrink-0">
        {lockedPage !== undefined ? (
          <span className="w-full text-center text-gray-500">
            Page {lockedPage + 1} (single-page job)
          </span>
        ) : (
          <>
            <button
              onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
              disabled={currentPage === 0}
              className="p-1 rounded hover:bg-gray-200 disabled:opacity-30 transition-colors"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <span>
              Page {totalPages ? currentPage + 1 : "—"} / {totalPages || "—"}
            </span>

            <button
              onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
              disabled={currentPage >= totalPages - 1}
              className="p-1 rounded hover:bg-gray-200 disabled:opacity-30 transition-colors"
              aria-label="Next page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
