import type { NextConfig } from "next";
import path from "path";
import { copyFileSync, mkdirSync } from "fs";

// Copy pdfjs worker to public/ so it's served as a static asset
try {
  const workerSrc = path.join(
    __dirname,
    "node_modules/pdfjs-dist/build/pdf.worker.min.mjs",
  );
  const workerDest = path.join(__dirname, "public/pdf.worker.min.mjs");
  mkdirSync(path.dirname(workerDest), { recursive: true });
  copyFileSync(workerSrc, workerDest);
} catch {
  // Non-fatal: worker may already be copied
}

const nextConfig: NextConfig = {
  output: "standalone",
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  },
  // Allow pdfjs worker to be served
  async headers() {
    return [
      {
        source: "/pdf.worker.min.mjs",
        headers: [{ key: "Content-Type", value: "text/javascript" }],
      },
    ];
  },
};

export default nextConfig;
