/**
 * Fetch a signed gallery image and trigger a browser file download.
 * Uses same-origin /api paths when possible (Vite/nginx proxy) so dev and Docker work.
 */

/**
 * @param {string} absoluteOrRelativeUrl
 * @returns {string}
 */
export function toSameOriginGalleryUrl(absoluteOrRelativeUrl) {
  if (!absoluteOrRelativeUrl) return absoluteOrRelativeUrl;
  try {
    const u = new URL(absoluteOrRelativeUrl, window.location.origin);
    if (u.pathname.includes("/gallery/raw/")) {
      return `${u.pathname}${u.search}`;
    }
  } catch {
    /* keep original */
  }
  return absoluteOrRelativeUrl;
}

/**
 * @param {{ url: string, filename?: string | null }} opts
 * @returns {Promise<void>}
 */
export async function downloadImageFromUrl({ url, filename }) {
  if (!url) {
    throw new Error("No image URL to download.");
  }
  const fetchUrl = toSameOriginGalleryUrl(url);
  const res = await fetch(fetchUrl);
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error("Download link expired. Generate again or reload the gallery.");
    }
    throw new Error(`Download failed (${res.status}).`);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const safeName = (filename || "rankify_image.png").replace(/[^\w.\-]+/g, "_");
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = safeName;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
