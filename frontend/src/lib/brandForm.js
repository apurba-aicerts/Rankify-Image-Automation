import { DEFAULT_GOVERNANCE_TEMPLATE, DEFAULT_SLIDE_SUFFIX } from "../constants/defaults.js";

function splitCsv(s) {
  return String(s || "")
    .split(/[,;\n]+/)
    .map((x) => x.trim())
    .filter(Boolean);
}

/** Serialize platform_hints.hints for the wizard (one "platform: hint" per line). */
export function hintsToLines(hints) {
  if (!hints || typeof hints !== "object") return "";
  return Object.entries(hints)
    .map(([k, v]) => `${k}: ${String(v || "").trim()}`)
    .filter((line) => line.length > 2)
    .join("\n");
}

/** Parse "platform: hint" lines into a hints object. */
export function parseHintsLines(s) {
  const out = {};
  for (const line of String(s || "").split("\n")) {
    const idx = line.indexOf(":");
    if (idx <= 0) continue;
    const k = line.slice(0, idx).trim().toLowerCase();
    const v = line.slice(idx + 1).trim();
    if (k) out[k] = v;
  }
  return out;
}

/**
 * Build POST /api/brands body from wizard form state.
 */
export function buildBrandCreatePayload(form) {
  const brand_id = (form.brand_id || "").trim().toLowerCase();
  const display_name = form.display_name.trim();
  if (!display_name) {
    throw new Error("Display name is required.");
  }
  if (brand_id && brand_id.length < 2) {
    throw new Error("Brand ID must be at least 2 characters (e.g. my-brand).");
  }
  const gov = (form.governance_prompt_template || "").trim();
  if (gov.length < 20) {
    throw new Error("Governance prompt must be at least 20 characters.");
  }

  return {
    ...(brand_id ? { brand_id } : {}),
    display_name,
    tagline: form.tagline.trim(),
    legal_suffix: form.legal_suffix.trim(),
    logo_asset_filename: form.logo_asset_filename.trim() || "logo.png",
    colors: {
      primary: splitCsv(form.colors_primary),
      secondary: splitCsv(form.colors_secondary),
      usage_rules: form.colors_usage_rules.trim(),
    },
    typography: {
      primary_font: form.typography_primary_font.trim(),
      headline_font: form.typography_headline_font.trim(),
      body_font: form.typography_body_font.trim(),
      notes: form.typography_notes.trim(),
    },
    voice: {
      tone_keywords: splitCsv(form.voice_tone_keywords),
      writing_style: form.voice_writing_style.trim(),
      target_audience: form.voice_target_audience.trim(),
    },
    social_defaults: {
      preferred_platforms: splitCsv(form.social_platforms),
      default_aspect_ratio: form.default_aspect_ratio || "1:1",
      default_image_size: form.default_image_size || "2K",
    },
    platform_hints: { hints: parseHintsLines(form.platform_hints_lines) },
    content_themes: {
      categories: splitCsv(form.content_categories),
      recurring_themes: splitCsv(form.content_themes),
    },
    text_preferences: {
      hashtag_style: form.hashtag_style.trim(),
      caption_style: form.caption_style.trim(),
      banned_phrases: splitCsv(form.banned_phrases),
    },
    generation: {
      governance_prompt_template: gov,
      design_guidelines: form.design_guidelines.trim(),
      layout_spacing_rules: (form.layout_spacing_rules || "").trim(),
      cta_button_rules: (form.cta_button_rules || "").trim(),
      visual_style_rules: (form.visual_style_rules || "").trim(),
      avoid_rules: (form.avoid_rules || "").trim(),
      slide_intro_template: form.slide_intro_template.trim(),
      slide_user_prompt_suffix:
        form.slide_user_prompt_suffix.trim() || DEFAULT_SLIDE_SUFFIX,
    },
  };
}

export function emptyBrandForm() {
  return {
    brand_id: "",
    display_name: "",
    tagline: "",
    legal_suffix: "",
    logo_asset_filename: "logo.png",
    colors_primary: "#1a1a2e, #cfa935",
    colors_secondary: "",
    colors_usage_rules: "",
    typography_primary_font: "Inter",
    typography_headline_font: "Montserrat",
    typography_body_font: "Open Sans",
    typography_notes: "",
    voice_tone_keywords: "Professional, Modern",
    voice_writing_style: "",
    voice_target_audience: "",
    social_platforms: "linkedin, instagram",
    default_aspect_ratio: "1:1",
    default_image_size: "2K",
    content_categories: "Product, Education",
    content_themes: "",
    hashtag_style: "",
    caption_style: "",
    banned_phrases: "",
    platform_hints_lines: "",
    governance_prompt_template: DEFAULT_GOVERNANCE_TEMPLATE,
    design_guidelines: "",
    layout_spacing_rules: "",
    cta_button_rules: "",
    visual_style_rules: "",
    avoid_rules: "",
    slide_intro_template: "",
    slide_user_prompt_suffix: DEFAULT_SLIDE_SUFFIX,
  };
}

/** Map GET /api/brands/:id into editable form fields */
export function brandToForm(brand) {
  const f = emptyBrandForm();
  f.brand_id = brand.brand_id;
  f.display_name = brand.display_name || "";
  f.tagline = brand.tagline || "";
  f.legal_suffix = brand.legal_suffix || "";
  f.logo_asset_filename = brand.logo_asset_filename || "logo.png";
  f.colors_primary = (brand.colors?.primary || []).join(", ");
  f.colors_secondary = (brand.colors?.secondary || []).join(", ");
  f.colors_usage_rules = brand.colors?.usage_rules || "";
  f.typography_primary_font = brand.typography?.primary_font || "";
  f.typography_headline_font = brand.typography?.headline_font || "";
  f.typography_body_font = brand.typography?.body_font || "";
  f.typography_notes = brand.typography?.notes || "";
  f.voice_tone_keywords = (brand.voice?.tone_keywords || []).join(", ");
  f.voice_writing_style = brand.voice?.writing_style || "";
  f.voice_target_audience = brand.voice?.target_audience || "";
  f.social_platforms = (brand.social_defaults?.preferred_platforms || []).join(", ");
  f.default_aspect_ratio = brand.social_defaults?.default_aspect_ratio || "1:1";
  f.default_image_size = brand.social_defaults?.default_image_size || "2K";
  f.content_categories = (brand.content_themes?.categories || []).join(", ");
  f.content_themes = (brand.content_themes?.recurring_themes || []).join(", ");
  f.hashtag_style = brand.text_preferences?.hashtag_style || "";
  f.caption_style = brand.text_preferences?.caption_style || "";
  f.banned_phrases = (brand.text_preferences?.banned_phrases || []).join(", ");
  f.platform_hints_lines = hintsToLines(brand.platform_hints?.hints);
  f.governance_prompt_template =
    brand.generation?.governance_prompt_template || DEFAULT_GOVERNANCE_TEMPLATE;
  f.design_guidelines = brand.generation?.design_guidelines || "";
  f.layout_spacing_rules = brand.generation?.layout_spacing_rules || "";
  f.cta_button_rules = brand.generation?.cta_button_rules || "";
  f.visual_style_rules = brand.generation?.visual_style_rules || "";
  f.avoid_rules = brand.generation?.avoid_rules || "";
  f.slide_intro_template = brand.generation?.slide_intro_template || "";
  f.slide_user_prompt_suffix =
    brand.generation?.slide_user_prompt_suffix || DEFAULT_SLIDE_SUFFIX;
  return f;
}

/** Map POST /api/brands/ai-draft ``draft`` object into wizard form fields. */
export function draftPayloadToForm(draft) {
  return brandToForm(draft);
}

/** Full body for PUT /api/brands/{brand_id} (BrandConfiguration). */
export function buildBrandPutConfiguration(form) {
  const payload = buildBrandCreatePayload(form);
  return {
    ...payload,
    updated_at: new Date().toISOString(),
  };
}
