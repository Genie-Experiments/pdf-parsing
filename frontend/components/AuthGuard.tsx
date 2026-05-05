"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { getMe } from "@/lib/api";
import { isDevBypass } from "@/lib/auth";

interface AuthGuardProps {
  children: React.ReactNode;
}

/**
 * Wraps any page that requires authentication.
 *
 * On mount, calls GET /auth/me (sends the httpOnly session cookie automatically).
 * - 200 → render children
 * - 401/403 or network error → redirect to /login
 * - DEV_BYPASS_AUTH=true → skip the check entirely (cookie not required)
 */
export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  // Skip network check immediately in dev bypass mode
  const [ready, setReady] = useState<boolean>(isDevBypass());

  useEffect(() => {
    if (isDevBypass()) return;

    getMe()
      .then(() => setReady(true))
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!ready) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />
      </div>
    );
  }

  return <>{children}</>;
}
