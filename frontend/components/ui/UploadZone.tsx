"use client";

import { useCallback, useState } from "react";
import { Upload } from "lucide-react";

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

export function UploadZone({ onFile, disabled }: Props) {
  const [dragging, setDragging] = useState(false);

  const handle = useCallback(
    (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) return;
      onFile(file);
    },
    [onFile],
  );

  return (
    <label
      className={[
        "flex flex-col items-center justify-center gap-4 w-full h-56 rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer",
        dragging
          ? "border-indigo-400 bg-indigo-50 scale-[1.01]"
          : "border-gray-200 bg-gray-50 hover:border-indigo-300 hover:bg-indigo-50/40",
        disabled ? "opacity-40 pointer-events-none" : "",
      ].join(" ")}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) handle(file);
      }}
    >
      <input
        type="file"
        accept=".pdf"
        className="sr-only"
        disabled={disabled}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handle(file);
        }}
      />
      <div
        className={[
          "w-14 h-14 rounded-2xl flex items-center justify-center transition-colors duration-200",
          dragging ? "bg-indigo-100" : "bg-white border border-gray-200 shadow-sm",
        ].join(" ")}
      >
        <Upload
          className={[
            "w-6 h-6 transition-colors duration-200",
            dragging ? "text-indigo-600" : "text-gray-400",
          ].join(" ")}
        />
      </div>
      <div className="text-center space-y-1">
        <p className="text-sm font-medium text-gray-700">
          {dragging ? "Drop to upload" : "Drop your PDF here"}
        </p>
        <p className="text-xs text-gray-400">or click to browse · PDF files only</p>
      </div>
    </label>
  );
}
