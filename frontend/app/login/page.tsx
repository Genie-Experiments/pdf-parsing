"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { isDevBypass } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export default function LoginPage() {
  const router = useRouter();

  useEffect(() => {
    if (isDevBypass()) router.replace("/");
  }, [router]);

  return (
    <main className="flex-1 bg-white text-gray-900 flex items-center justify-center">
      <div className="flex flex-col items-center gap-6 max-w-sm w-full px-6">
        {/* Logo + heading */}
        <div className="flex flex-row items-center justify-center gap-4">
          <Image
            src="/logo-genie-cropped.png"
            alt="Genie"
            width={120}
            height={60}
            className="object-contain self-center"
            style={{ display: "block" }}
          />
          <h1 className="text-2xl font-bold text-gray-800 tracking-tight self-center mt-[20px] whitespace-nowrap">GenieParse</h1>
        </div>

        {/* Subtitle */}
        <p className="text-sm text-gray-500 text-center">
          Sign in with your @emumba.com account to continue.
        </p>

        {/* Google sign-in button */}
        <a
          href={`${API_BASE}/auth/login`}
          className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg bg-white text-gray-800 font-medium hover:bg-gray-50 active:bg-gray-100 transition-colors shadow-sm border border-gray-200"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z" />
            <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2.04a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z" />
            <path fill="#FBBC05" d="M4.5 10.48A4.8 4.8 0 0 1 4.5 7.5V5.44H1.83a8 8 0 0 0 0 7.11z" />
            <path fill="#EA4335" d="M8.98 3.58c1.32 0 2.5.45 3.44 1.35l2.54-2.54A8 8 0 0 0 1.83 5.44L4.5 7.5c.69-2.07 2.64-3.92 4.48-3.92z" />
          </svg>
          Sign in with Google
        </a>

        <p className="text-xs text-gray-400">
          Access is restricted to @emumba.com accounts.
        </p>
      </div>
    </main>
  );
}
