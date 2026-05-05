/**
 * Auth helpers for the frontend.
 *
 * The JWT session lives exclusively in an httpOnly cookie managed by the backend.
 * JavaScript never reads or writes the token — this eliminates XSS token theft.
 *
 * The only client-side auth concern is whether to show the login gate or not,
 * which is handled by calling GET /auth/me (returns 200 = authenticated, 401 = not).
 */

/** True when DEV_BYPASS_AUTH is set — login page is skipped and /auth/me is not called. */
export function isDevBypass(): boolean {
  return process.env.NEXT_PUBLIC_DEV_BYPASS_AUTH === "true";
}
