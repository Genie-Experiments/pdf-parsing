"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock, Download, Loader2 } from "lucide-react";
import { PdfViewer } from "@/components/pdf-viewer/PdfViewer";
import { MarkdownPanel } from "@/components/markdown-viewer/MarkdownPanel";
import { StepProgress } from "@/components/ui/StepProgress";
import { BASE, getJob, getJobResult, JobResult } from "@/lib/api";
import { AuthGuard } from "@/components/AuthGuard";

type View = "preview" | "raw";

function downloadMarkdown(markdown: string, filename: string) {
  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.replace(/\.pdf$/i, ".md");
  a.click();
  URL.revokeObjectURL(url);
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();

  const [result, setResult] = useState<JobResult | null>(null);
  const [view, setView] = useState<View>("preview");
  const pdfUrl = `${BASE}/jobs/${id}/pdf/content`;
  const { data: job } = useQuery({
    queryKey: ["job", id],
    queryFn: () => getJob(id),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "done" || s === "failed" || s === "cancelled" ? false : 2000;
    },
  });


  // Fetch result (markdown) once done
  useEffect(() => {
    if (job?.status !== "done" || result) return;
    getJobResult(id).then(setResult);
  }, [id, job?.status, result]);

  const isRunning = job?.status === "queued" || job?.status === "running";
  const currentStep = job?.current_step ?? 0;

  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!job) return;
    const terminal = job.status === "done" || job.status === "failed" || job.status === "cancelled";
    if (terminal) {
      setElapsed(Math.round((new Date(job.updated_at).getTime() - new Date(job.created_at).getTime()) / 1000));
      return;
    }
    const start = new Date(job.created_at).getTime();
    const tick = () => setElapsed(Math.round((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [job?.status, job?.created_at, job?.updated_at]);

  function formatElapsed(s: number) {
    if (s < 60) return `${s}s`;
    return `${Math.floor(s / 60)}m ${s % 60}s`;
  }

  const handleDownload = useCallback(() => {
    if (result && job) downloadMarkdown(result.markdown, job.filename);
  }, [result, job]);

  return (
    <AuthGuard>
      <div className="flex h-screen bg-white text-gray-900 overflow-hidden">

        {/* ── Left: nav + PDF viewer ────────────────────────────────────── */}
        <div className="w-1/2 border-r border-gray-200 flex flex-col overflow-hidden">

          {/* Nav bar */}
          <div className="flex items-center gap-2 px-3 py-3 border-b border-gray-200 shrink-0">
            <button
              onClick={() => router.push("/")}
              className="p-1.5 rounded hover:bg-gray-100 transition-colors shrink-0"
              aria-label="Back"
            >
              <ArrowLeft className="w-4 h-4 text-gray-500" />
            </button>
            <span className="text-sm font-medium truncate flex-1 text-gray-800">
              {job?.filename ?? "Loading…"}
            </span>
            <span className={[
              "text-xs px-2 py-0.5 rounded-full border font-medium shrink-0 flex items-center gap-1",
              job?.status === "done"      ? "border-green-300 text-green-700 bg-green-50"    :
              job?.status === "failed"    ? "border-red-300 text-red-700 bg-red-50"          :
              job?.status === "running"   ? "border-indigo-300 text-indigo-700 bg-indigo-50" :
              job?.status === "cancelled" ? "border-amber-300 text-amber-700 bg-amber-50"    :
              "border-gray-300 text-gray-500 bg-gray-50",
            ].join(" ")}>
              {job?.status === "running" && <Loader2 className="w-3 h-3 animate-spin" />}
              {job?.status ?? "…"}
            </span>
            {job && elapsed > 0 && (
              <span className="text-xs text-gray-400 shrink-0 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatElapsed(elapsed)}
              </span>
            )}
          </div>

          {/* PDF */}
          <div className="flex-1 overflow-hidden">
            {job ? (
              <PdfViewer
                pdfUrl={pdfUrl}
                lockedPage={job.page != null ? job.page - 1 : undefined}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="w-6 h-6 text-gray-300 animate-spin" />
              </div>
            )}
          </div>
        </div>

        {/* ── Right: steps while running, markdown when done ────────────── */}
        <div className="w-1/2 flex flex-col overflow-hidden">

          {/* Toolbar — only when markdown is ready */}
          {result && (
            <div className="flex items-center gap-2 px-3 py-3 border-b border-gray-200 shrink-0">
              <div className="flex rounded-lg border border-gray-300 overflow-hidden text-xs">
                {(["preview", "raw"] as View[]).map((v) => (
                  <button
                    key={v}
                    onClick={() => setView(v)}
                    className={[
                      "px-3 py-1.5 capitalize transition-colors",
                      view === v ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-gray-700 hover:bg-gray-50",
                    ].join(" ")}
                  >
                    {v}
                  </button>
                ))}
              </div>
              <div className="flex-1" />
              <button
                onClick={handleDownload}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-gray-300 text-gray-500 hover:text-gray-700 hover:border-gray-400 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Download</span>
              </button>
            </div>
          )}

          {/* Content: steps, markdown, or cancelled notice */}
          <div className="flex-1 overflow-hidden">
            {result ? (
              <MarkdownPanel markdown={result.markdown} view={view} />
            ) : job?.status === "cancelled" ? (
              <div className="flex items-center justify-center h-full">
                <p className="text-sm text-amber-600">Job was cancelled.</p>
              </div>
            ) : (
              <StepProgress currentStep={currentStep} isRunning={isRunning} />
            )}
          </div>

          {/* Failed message */}
          {job?.status === "failed" && (
            <div className="px-4 py-3 border-t border-red-100 bg-red-50 text-xs text-red-700 shrink-0">
              Pipeline failed.
              {job.error_message && (
                <span className="block mt-0.5 text-red-600">{job.error_message}</span>
              )}
            </div>
          )}
        </div>


      </div>
    </AuthGuard>
  );
}
