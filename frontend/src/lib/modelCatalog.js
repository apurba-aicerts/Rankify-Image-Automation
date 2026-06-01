/**
 * Helpers for /api/models catalog entries.
 * @typedef {{ model_name: string, provider?: string, label?: string, supports_image_size?: boolean }} ImageModelEntry
 */

/** @param {ImageModelEntry[]} catalog @param {string} modelName */
export function findModelEntry(catalog, modelName) {
  return catalog.find((m) => m.model_name === modelName) ?? null;
}

/** @param {ImageModelEntry[]} catalog @param {string} modelName */
export function modelSupportsImageSize(catalog, modelName) {
  const row = findModelEntry(catalog, modelName);
  if (row) return Boolean(row.supports_image_size);
  return modelName === "gemini-3-pro-image-preview";
}

/** @param {ImageModelEntry} row */
export function modelOptionLabel(row) {
  if (row.label) return row.label;
  if (row.provider === "openai") return `OpenAI — ${row.model_name.replace(/^openai:/, "")}`;
  if (row.provider === "gemini") return `Gemini — ${row.model_name}`;
  return row.model_name;
}
