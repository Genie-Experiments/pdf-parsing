"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { FileText, Clock, CheckCircle, XCircle, Loader2, AlertTriangle, LogOut, User, Ban } from "lucide-react";
import Image from "next/image";
import { UploadZone } from "@/components/ui/UploadZone";
import { JobOptions, JobConfig } from "@/components/ui/JobOptions";
import { AuthGuard } from "@/components/AuthGuard";
import { uploadPdf, listJobs, getJobStats, getMe, logout, Job, JobStatus, JobStats } from "@/lib/api";

const statusMeta: Record<JobStatus, { icon: React.ReactNode; label: string; dotClass: string }> = {
  queued:    { icon: <Clock className="w-3.5 h-3.5 text-gray-400" />,                   label: "Queued",    dotClass: "bg-gray-300" },
  running:   { icon: <Loader2 className="w-3.5 h-3.5 text-indigo-500 animate-spin" />,  label: "Running",   dotClass: "bg-indigo-400 animate-pulse" },
  done:      { icon: <CheckCircle className="w-3.5 h-3.5 text-green-500" />,            label: "Done",      dotClass: "bg-green-400" },
  failed:    { icon: <XCircle className="w-3.5 h-3.5 text-red-500" />,                  label: "Failed",    dotClass: "bg-red-400" },
  cancelled: { icon: <Ban className="w-3.5 h-3.5 text-amber-400" />,                    label: "Cancelled", dotClass: "bg-amber-300" },
};

const PIPELINE_STEPS = [
  { title: "PDF Parsing",            desc: "AI model converts each page to structured text & images" },
  { title: "Text Extraction",        desc: "Raw PDF text saved as an accuracy reference" },
  { title: "Structure Detection",    desc: "Font metrics used to detect the heading hierarchy" },
  { title: "Content Backup",         desc: "Markdown files copied before any edits are applied" },
  { title: "Segment Refinement",     desc: "Tables, code blocks, and figures polished separately" },
  { title: "Page Breaks",            desc: "Page boundary markers inserted throughout the document" },
  { title: "Header & Footer Removal",desc: "Repetitive cross-page content detected and stripped" },
  { title: "OCR Correction",         desc: "Errors fixed by fuzzy-matching against raw PDF text" },
  { title: "Hierarchy Fix",          desc: "Heading levels corrected using the detected structure" },
  { title: "Bullet Standardization", desc: "Bullet symbols (•, ◦, etc.) normalized to Markdown" },
];

const LIMITATIONS = [
  "Table of Contents sections are not parsed correctly.",
  "Complex or multi-span tables may have inaccuracies.",
  "Code blocks without LLM refinement may lose indentation in edge cases.",
  "4-column or unusual page layouts may produce occasional OCR errors.",
];

export default function HomePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [scope, setScope] = useState<"mine" | "all">("all");
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getMe().then((u) => setUserEmail(u.email)).catch(() => {});
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const { data: jobs = [] } = useQuery<Job[]>({
    queryKey: ["jobs", scope],
    queryFn: () => listJobs(scope),
    refetchInterval: 5000,
  });

  const { data: stats } = useQuery<JobStats>({
    queryKey: ["job-stats", scope],
    queryFn: () => getJobStats(scope),
    refetchInterval: 10000,
  });

  const upload = useMutation({
    mutationFn: ({ file, page, segmentsToRefine }: JobConfig) =>
      uploadPdf(file, { page, segmentsToRefine }),
    onSuccess: (job) => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      router.push(`/jobs/${job.id}`);
    },
  });

  return (
    <AuthGuard>
      <main className="min-h-screen bg-gray-50 text-gray-900">

        {/* Upload hero */}
        <div className="bg-white border-b border-gray-100 px-6 py-10 relative">
          {/* Profile / logout */}
          <div ref={profileRef} className="absolute top-4 right-4">
            <button
              onClick={() => setProfileOpen((o) => !o)}
              className="w-9 h-9 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center hover:bg-indigo-200 transition-colors"
              aria-label="Profile"
            >
              <User className="w-4 h-4" />
            </button>
            {profileOpen && (
              <div className="absolute right-0 mt-1 w-52 bg-white rounded-lg border border-gray-200 shadow-lg py-1 z-50">
                {userEmail && (
                  <p className="px-3 py-2 text-xs text-gray-500 border-b border-gray-100 truncate">{userEmail}</p>
                )}
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5 text-gray-400" />
                  Sign out
                </button>
              </div>
            )}
          </div>

          <div className="max-w-xl mx-auto space-y-5">
            <div className="flex flex-row items-center justify-center gap-4">
              <Image
                src="/logo-genie-cropped.png"
                alt="Genie"
                width={120}
                height={60}
                className="object-contain self-center"
                style={{ display: "block" }}
              />
              <h1 className="text-2xl font-bold text-gray-800 tracking-tight self-center mt-[20px]">GenieParse</h1>
            </div>

            <AnimatePresence mode="wait">
              {selectedFile ? (
                <motion.div
                  key="options"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.18 }}
                >
                  <JobOptions
                    file={selectedFile}
                    onSubmit={(config) => upload.mutate(config)}
                    onCancel={() => { setSelectedFile(null); upload.reset(); }}
                    disabled={upload.isPending}
                  />
                </motion.div>
              ) : (
                <motion.div
                  key="upload"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.18 }}
                >
                  <UploadZone onFile={setSelectedFile} disabled={upload.isPending} />
                </motion.div>
              )}
            </AnimatePresence>

            {stats && (
              <p className="text-[11px] text-center text-gray-400">
                <span className="text-black-600 font-medium">{scope === "all" ? "GenieParse has got" : "You have"} </span>
                {" · "}
                <span className="text-green-600 font-medium">{stats.done} done</span>
                {" · "}
                <span className="text-indigo-500 font-medium">{stats.running} running</span>
                {" · "}
                <span className="text-gray-500 font-medium">{stats.queued} queued</span>
                {stats.failed > 0 && (
                  <>{" · "}<span className="text-red-400 font-medium">{stats.failed} failed</span></>
                )}
                {" · "}
                <span className="text-black-600 font-medium"> jobs in total</span>
              </p>
            )}

            {upload.isPending && (
              <p className="text-xs text-center text-indigo-500 flex items-center justify-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Uploading and queuing…
              </p>
            )}
            {upload.isError && (
              <p className="text-xs text-center text-red-500">
                Upload failed: {(upload.error as Error).message}
              </p>
            )}
          </div>
        </div>

        {/* Info section */}
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="flex flex-col lg:flex-row gap-8 items-start">

            {/* Left: How it works + Limitations — both same width */}
            <div className="flex-1 min-w-0 space-y-8">

              <section className="space-y-3">
                <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  How it works
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                  {PIPELINE_STEPS.map((step, i) => (
                    <div
                      key={i}
                      className="bg-white rounded-lg border border-gray-200 px-3 py-2.5 space-y-1 hover:border-indigo-200 hover:bg-indigo-50/20 transition-colors"
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="shrink-0 w-4 h-4 rounded-full bg-indigo-50 text-indigo-600 text-[9px] font-bold flex items-center justify-center">
                          {i + 1}
                        </span>
                        <span className="text-xs font-semibold text-gray-800 leading-tight">{step.title}</span>
                      </div>
                      <p className="text-[10px] text-gray-400 leading-relaxed">{step.desc}</p>
                    </div>
                  ))}
                </div>
              </section>

              <section className="space-y-2">
                <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Limitations
                </h2>
                <div className="bg-amber-50 border border-amber-100 rounded-lg p-4 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
                  {LIMITATIONS.map((item, i) => (
                    <div key={i} className="flex gap-2 text-xs text-amber-700">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
                      {item}
                    </div>
                  ))}
                </div>
              </section>

            </div>

            {/* Right: Recent jobs sidebar */}
            <div className="w-full lg:w-64 shrink-0 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Recent jobs
                </h2>
                <div className="flex items-center gap-0.5 bg-gray-100 rounded-md p-0.5">
                  <button
                    onClick={() => setScope("mine")}
                    className={`text-[10px] px-2 py-0.5 rounded transition-colors ${scope === "mine" ? "bg-white shadow-sm text-gray-800 font-medium" : "text-gray-400 hover:text-gray-600"}`}
                  >
                    Mine
                  </button>
                  <button
                    onClick={() => setScope("all")}
                    className={`text-[10px] px-2 py-0.5 rounded transition-colors ${scope === "all" ? "bg-white shadow-sm text-gray-800 font-medium" : "text-gray-400 hover:text-gray-600"}`}
                  >
                    All
                  </button>
                </div>
              </div>
              {stats && (
                <p className="text-[11px] text-gray-400">
                  <span className="text-green-600 font-medium">{stats.done} done</span>
                  {" · "}
                  <span className="text-indigo-500 font-medium">{stats.running} running</span>
                  {" · "}
                  <span className="font-medium">{stats.queued} queued</span>
                  {" jobs"}
                </p>
              )}
              {jobs.length === 0 ? (
                <div className="rounded-lg border border-dashed border-gray-200 bg-white p-6 text-center">
                  <FileText className="w-6 h-6 text-gray-300 mx-auto mb-2" />
                  <p className="text-xs text-gray-400">No jobs yet</p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {jobs.map((job) => {
                    const meta = statusMeta[job.status];
                    const isOwn = job.user_email === userEmail;
                    const clickable = scope === "mine" || isOwn;
                    return (
                      <li key={job.id}>
                        <button
                          onClick={() => clickable ? router.push(`/jobs/${job.id}`) : undefined}
                          className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg bg-white border border-gray-200 transition-colors text-left ${clickable ? "hover:border-indigo-200 hover:bg-indigo-50/30 cursor-pointer" : "cursor-default opacity-70"}`}
                        >
                          <span className={`shrink-0 w-2 h-2 rounded-full ${meta.dotClass}`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-gray-800 truncate">{job.filename}</p>
                            {scope === "all" && (
                              <p className="text-[10px] text-indigo-400 truncate">{job.user_email}</p>
                            )}
                            <p className="text-[10px] text-gray-400 mt-0.5">{meta.label}</p>
                          </div>
                          {meta.icon}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

          </div>
        </div>
      </main>
    </AuthGuard>
  );
}
