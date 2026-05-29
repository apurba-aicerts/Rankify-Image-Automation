const LS_BASE = "rankify_api_base";
const LS_KEY = "rankify_api_key";

function envApiBase() {
  const v = import.meta.env?.VITE_API_BASE;
  return typeof v === "string" && v.trim() ? v.trim().replace(/\/+$/, "") : "";
}

function envApiKey() {
  const v = import.meta.env?.VITE_API_KEY;
  return typeof v === "string" ? v : "";
}

/** Default API origin: in dev, empty string uses Vite proxy (same tab origin → no CORS). */
function defaultApiBase() {
  const fromEnv = envApiBase();
  if (fromEnv) return fromEnv;
  if (import.meta.env?.DEV) return "";
  return "http://localhost:9600";
}

export function loadStoredSettings() {
  const rawBase = localStorage.getItem(LS_BASE);
  const rawKey = localStorage.getItem(LS_KEY);
  const base = rawBase === null ? defaultApiBase() : rawBase;
  return {
    apiBase: base.replace(/\/+$/, ""),
    apiKey: rawKey === null ? envApiKey() : rawKey,
  };
}

export function persistSettings(apiBase, apiKey) {
  localStorage.setItem(LS_BASE, apiBase.trim().replace(/\/+$/, ""));
  localStorage.setItem(LS_KEY, apiKey);
}

/**
 * @param {{ apiBase: string, apiKey: string }} creds
 */
export function createApiClient({ apiBase, apiKey }) {
  const base = apiBase.replace(/\/+$/, "");

  /**
   * @param {string} path
   * @param {{ method?: string, json?: unknown, headers?: Record<string,string> }} [opts]
   */
  async function request(path, opts = {}) {
    const { method = "GET", json, headers = {} } = opts;
    const url = path.startsWith("http") ? path : `${base}${path}`;
    const h = { ...headers };
    const publicPath =
      path.includes("/health") ||
      url.includes("/health") ||
      url.includes("/gallery/raw");
    if (!publicPath) {
      if (!apiKey) throw new Error("Configure your API key in Settings.");
      h["x-api-key"] = apiKey;
    }
    let res;
    try {
      res = await fetch(url, {
        method,
        headers:
          json !== undefined
            ? { ...h, "Content-Type": "application/json" }
            : h,
        body: json !== undefined ? JSON.stringify(json) : undefined,
      });
    } catch (e) {
      const devProxy = import.meta.env?.DEV && !base;
      const hint = devProxy
        ? " Is the FastAPI server running (e.g. uvicorn on :9600)? The dev app proxies /api to it."
        : import.meta.env?.DEV && base.startsWith("http")
          ? " Tip: in dev, clear API base (empty = Vite proxy) or fix the URL."
          : " Check that the API server is running and Settings → API base URL is correct.";
      if (e instanceof TypeError) {
        throw new Error(`Network error calling ${url || path}.${hint} (${e.message})`);
      }
      throw e;
    }
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!res.ok) {
      const msg =
        data && typeof data === "object" && "detail" in data
          ? JSON.stringify(data.detail)
          : text || res.statusText;
      const err = new Error(`${res.status}: ${msg}`);
      err.status = res.status;
      err.body = data;
      throw err;
    }
    return data;
  }

  /**
   * Fetch brand logo bytes (requires API key). Returns a blob object URL or null if missing.
   * Caller must revoke the URL when unmounting.
   * @param {string} brandId
   */
  async function fetchBrandLogoObjectUrl(brandId) {
    const path = `/api/brands/${encodeURIComponent(brandId)}/assets/logo`;
    const url = `${base}${path}`;
    if (!apiKey) return null;
    const res = await fetch(url, { headers: { "x-api-key": apiKey } });
    if (res.status === 404) return null;
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text || res.statusText}`);
    }
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  }

  return { base, request, fetchBrandLogoObjectUrl };
}
