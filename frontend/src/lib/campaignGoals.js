/** Campaign-first goals — map to labels for assembly + UI. */
export const CAMPAIGN_GOALS = [
  { id: "brand_awareness", label: "Brand awareness" },
  { id: "webinar", label: "Webinar promotion" },
  { id: "product_launch", label: "Product launch" },
  { id: "hiring", label: "Hiring" },
  { id: "event_countdown", label: "Event countdown" },
  { id: "educational_carousel", label: "Educational carousel" },
  { id: "founder", label: "Founder branding" },
  { id: "blog", label: "Blog promotion" },
  { id: "cert_launch", label: "AI certification launch" },
  { id: "student_story", label: "Student success story" },
];

export const STUDIO_PLATFORMS = [
  { id: "linkedin", label: "LinkedIn" },
  { id: "instagram", label: "Instagram" },
  { id: "x", label: "X" },
  { id: "facebook", label: "Facebook" },
  { id: "threads", label: "Threads" },
  { id: "tiktok", label: "TikTok" },
  { id: "youtube", label: "YouTube" },
];

export const PROMPT_ASSIST_SNIPPETS = [
  { label: "Bold hero section", chip: "Bold hero", text: "\n• Open with a bold hero headline and high-contrast focal visual." },
  { label: "Stats slide", chip: "Stats card", text: "\n• Include one credible statistic or proof point with clear typography." },
  { label: "CTA slide", chip: "CTA", text: "\n• Close with a single dominant CTA and minimal competing elements." },
  { label: "Quote card", chip: "Quote slide", text: "\n• Feature a short authority quote with attribution and editorial layout." },
  { label: "Timeline", chip: "Timeline", text: "\n• Show a simple 3-step timeline: before → shift → after." },
  { label: "Comparison slide", chip: "Compare", text: "\n• Side-by-side comparison: old way vs new way; keep labels legible." },
  { label: "Founder message", chip: "Founder", text: "\n• Founder-style message: personal tone, signature, warm lighting." },
];

/** Copy tone for the studio dropdown (separate from AI creativity slider). */
export const STUDIO_VOICE_TONES = [
  { id: "professional", label: "Professional" },
  { id: "modern", label: "Modern" },
  { id: "minimal", label: "Minimal" },
  { id: "bold", label: "Bold" },
  { id: "educational", label: "Educational" },
];

export function goalLabel(goalId) {
  return CAMPAIGN_GOALS.find((g) => g.id === goalId)?.label || "Campaign";
}

/** Map slider 0–100 to copy the model understands. */
export function toneLabelFromBias(bias) {
  if (bias < 34) return "Faithful — strict adherence to brand system";
  if (bias < 67) return "Balanced — on-brand with light creative stretch";
  return "Wild — bold compositions while respecting palette & logo";
}

/** Short label under the AI creativity slider (Faithful → Wild). */
export function creativityBiasShort(bias) {
  if (bias < 34) return "Faithful";
  if (bias < 67) return "Balanced";
  return "Wild";
}
