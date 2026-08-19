/**
 * Opinionated creative direction bullets for the studio panel (trust layer).
 * Derived from persisted brand JSON + studio tone bias.
 */

export function buildCreativeDirectionBullets(brand, toneBias) {
  const lines = [];
  if (!brand) {
    lines.push("Load brand rules to preview creative direction.");
    return lines;
  }

  const prim = (brand.colors?.primary || []).filter(Boolean);
  if (prim.length) lines.push(`Palette led by ${prim.slice(0, 2).join(" & ")} with disciplined contrast.`);

  const usage = (brand.colors?.usage_rules || "").trim();
  if (usage) lines.push(usage.length > 90 ? `${usage.slice(0, 87)}…` : usage);

  const h = (brand.typography?.headline_font || "").trim();
  const b = (brand.typography?.body_font || "").trim();
  if (h || b) lines.push(`Typography: ${[h, b].filter(Boolean).join(" over ")} hierarchy.`);

  const notes = (brand.typography?.notes || "").trim();
  if (notes) lines.push(notes.length > 100 ? `${notes.slice(0, 97)}…` : notes);

  const tone = (brand.voice?.tone_keywords || []).slice(0, 4);
  if (tone.length) lines.push(`Voice: ${tone.join(", ").toLowerCase()} delivery.`);

  const dg = (brand.generation?.design_guidelines || "").trim();
  if (dg) lines.push(dg.length > 110 ? `${dg.slice(0, 107)}…` : dg);

  if (toneBias >= 66) lines.push("Studio bias: allow bolder compositions and negative space experiments.");
  else if (toneBias <= 33) lines.push("Studio bias: stay conservative—tight adherence to brand guardrails.");
  else lines.push("Studio bias: balance brand fidelity with scroll-stopping clarity.");

  if (lines.length < 4) {
    lines.push("Premium editorial layouts with clear CTA hierarchy.");
    lines.push("Imagery should feel credible, modern, and campaign-coherent.");
  }
  return lines.slice(0, 8);
}

export function buildSocialIntelligenceTips({ platforms, campaignGoalId }) {
  const tips = [];
  if (platforms?.includes("linkedin")) {
    tips.push("LinkedIn: shorter headlines often outperform in feed—test a 6–9 word hook.");
  }
  if (campaignGoalId === "webinar") {
    tips.push("Webinar: include date/time in the creative when promoting a specific session.");
  }
  if (campaignGoalId === "hiring") {
    tips.push("Hiring: lead with culture or impact before role requirements.");
  }
  tips.push("Validate what resonates using each platform’s native analytics.");
  return tips.slice(0, 5);
}

export function buildCaptionHashtagDraft({ displayName, intent, platforms }) {
  const cap = `${displayName} — ${(intent || "").slice(0, 220)}${(intent || "").length > 220 ? "…" : ""}`.trim();
  const tags = ["#Brand", "#Marketing", "#SocialFirst"];
  (platforms || []).forEach((p) => {
    const t = p.replace(/\s+/g, "");
    if (t) tags.push(`#${t.charAt(0).toUpperCase() + t.slice(1)}`);
  });
  return { caption: cap, hashtags: tags.slice(0, 8).join(" ") };
}
