// Same-origin in development (Vite) and production (Vercel). An override includes /api.
export const ENGINE_BASE = (import.meta.env["VITE_ENGINE_URL"]?.trim() || "/api").replace(/\/+$/, "");
export const SESSION_EXPIRED = "morphy:session-expired";
