"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  lines: string[];
  isRunning: boolean;
}

function getLineColor(raw: string): string {
  if (raw.includes("[ERROR]") || raw.includes("✗")) return "text-red-600";
  if (raw.includes("[WARNING]") || raw.includes("[WARN]")) return "text-amber-600";
  if (/={3,}.*STEP\s+\d+/i.test(raw) || /STEP\s+\d+.*={3,}/i.test(raw)) return "text-indigo-600 font-semibold";
  if (raw.includes("✓")) return "text-green-600";
  return "text-gray-700";
}

/** Returns cleaned display text, or null to skip the line entirely. */
function cleanLine(raw: string): string | null {
  // Skip pure separator lines
  if (/^={5,}\s*$/.test(raw.trim())) return null;

  // Skip noisy internals
  if (/\[(?:INFO|WARNING|WARN|ERROR)\]\s+Running command:/i.test(raw)) return null;
  if (/\[(?:INFO|WARNING|WARN|ERROR)\]\s+Output directory:/i.test(raw)) return null;

  // Extract readable text from STEP banner lines: "=== STEP 1: Title ==="
  const stepMatch = raw.match(/={3,}\s*STEP\s+(\d+):\s*(.+?)\s*={0,}/i);
  if (stepMatch) return `Step ${stepMatch[1]}: ${stepMatch[2].trim()}`;

  // Strip log level prefix
  let text = raw.replace(/^\[(?:INFO|WARNING|WARN|ERROR)\]\s*/i, "");

  // Shorten absolute paths to just the filename
  text = text.replace(/(?:\/[^\s/]+)+\/([\w.\-]+\.(?:pdf|json|md|txt|py|log))/g, "$1");

  return text.trim() || null;
}

export function LogConsole({ lines, isRunning }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines.length]);

  const displayLines: { text: string; raw: string }[] = showRaw
    ? lines.map((l) => ({ text: l, raw: l }))
    : lines.flatMap((l) => {
        const text = cleanLine(l);
        return text ? [{ text, raw: l }] : [];
      });

  return (
    <div className="flex flex-col h-full bg-gray-50 rounded-lg border border-gray-200">
      {/* header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-white rounded-t-lg">
        {isRunning && (
          <span className="inline-block w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
        )}
        <span className="text-xs font-mono text-gray-500 flex-1">
          {isRunning ? "Pipeline running…" : "Pipeline output"}
        </span>
        <button
          onClick={() => setShowRaw((v) => !v)}
          className="text-[10px] text-gray-400 hover:text-gray-600 transition-colors px-1.5 py-0.5 rounded border border-gray-200 hover:border-gray-300 bg-white"
        >
          {showRaw ? "Clean" : "Raw"}
        </button>
      </div>

      {/* log lines */}
      <div className="flex-1 overflow-auto p-3 font-mono text-xs leading-relaxed">
        {displayLines.map(({ text, raw }, i) => (
          <div key={i} className={getLineColor(raw)}>
            {text}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
