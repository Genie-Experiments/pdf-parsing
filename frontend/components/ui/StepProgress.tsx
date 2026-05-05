"use client";

import { CheckCircle, Circle, Loader2 } from "lucide-react";

const STEPS = [
  "Dolphin inference",
  "Raw text extraction",
  "Section hierarchy",
  "Backup",
  "Segment refinement",
  "Insert page breaks",
  "Remove headers / footers",
  "Fix OCR errors",
  "Fix section hierarchy",
  "Standardize bullets",
];

interface Props {
  /** 1-based current step parsed from logs (0 = not started yet) */
  currentStep: number;
  /** True while the job is still running */
  isRunning: boolean;
}

export function StepProgress({ currentStep, isRunning }: Props) {
  return (
    <div className="flex flex-col h-full justify-center px-8 py-6 space-y-1">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
        Pipeline progress
      </p>
      {STEPS.map((label, i) => {
        const stepNum  = i + 1;
        const isDone   = stepNum < currentStep || (!isRunning && currentStep > 0);
        const isActive = stepNum === currentStep && isRunning;

        return (
          <div
            key={stepNum}
            className={[
              "flex items-center gap-3 py-1.5 px-2 rounded-lg transition-colors",
              isActive ? "bg-indigo-50" : "",
            ].join(" ")}
          >
            {/* icon */}
            <span className="shrink-0">
              {isDone ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : isActive ? (
                <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />
              ) : (
                <Circle className="w-4 h-4 text-gray-300" />
              )}
            </span>

            {/* step number + label */}
            <span
              className={[
                "text-sm",
                isDone   ? "text-gray-400 line-through decoration-gray-300" :
                isActive ? "text-indigo-600 font-medium" :
                           "text-gray-400",
              ].join(" ")}
            >
              <span className="text-xs mr-1.5 tabular-nums text-gray-400">{stepNum}.</span>
              {label}
            </span>
          </div>
        );
      })}

      {/* overall progress bar */}
      <div className="mt-5 space-y-1.5">
        <div className="h-1.5 w-full rounded-full bg-gray-200 overflow-hidden">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all duration-500"
            style={{ width: `${Math.min(100, ((currentStep - 1) / STEPS.length) * 100)}%` }}
          />
        </div>
        <p className="text-xs text-gray-400 text-right">
          {currentStep > 0
            ? `Step ${currentStep} of ${STEPS.length}`
            : "Waiting to start…"}
        </p>
      </div>
    </div>
  );
}
