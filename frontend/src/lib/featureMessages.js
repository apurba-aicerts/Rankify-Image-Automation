/** HTTP status used by the API for stub / not-yet-implemented endpoints. */
export const STATUS_NOT_IMPLEMENTED = 501;

/**
 * @param {unknown} err
 * @returns {boolean}
 */
export function isNotImplementedError(err) {
  return typeof err === "object" && err !== null && /** @type {{ status?: number }} */ (err).status === STATUS_NOT_IMPLEMENTED;
}

/**
 * Consistent feedback when a UI action is not wired up yet.
 * @param {(message: string, variant?: string) => void} showToast
 * @param {string} [featureName] e.g. "Edit with AI"
 */
export function toastComingSoon(showToast, featureName) {
  const name = (featureName || "").trim();
  const text = name ? `${name} — coming soon.` : "Coming soon.";
  showToast(text, "info");
}
