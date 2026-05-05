"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

/**
 * OAuth callback landing page.
 *
 * The backend has already validated the OAuth code, verified the @emumba.com
 * domain, and set the httpOnly session cookie in the redirect response.
 * This page has nothing to do — just redirect to the home page so the
 * AuthGuard can confirm the session is valid.
 *
 * Note: no token ever appears in the URL or in JavaScript.
 */
export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/");
  }, [router]);

  return (
    <main className="min-h-screen bg-gray-50 text-gray-700 flex items-center justify-center">
      <div className="flex items-center gap-3 text-gray-500 text-sm">
        <Loader2 className="w-4 h-4 animate-spin" />
        Completing sign-in…
      </div>
    </main>
  );
}
