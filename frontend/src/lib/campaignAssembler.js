/**
 * Build the `studio_campaign` object for POST /api/generate.
 * Image generation uses `intent` verbatim on the server; assembly below is for social-copy context.
 */
const DEFAULT_CAMPAIGN_GOAL_ID = "brand_awareness";

export function buildStudioCampaignPayload({
  platforms,
  voiceToneLabel,
  creativityToneLabel,
  intent,
}) {
  return {
    campaign_goal_id: DEFAULT_CAMPAIGN_GOAL_ID,
    platforms: (platforms || []).filter(Boolean).map((p) => String(p).toLowerCase()),
    voice_tone_label: (voiceToneLabel || "Professional").trim() || "Professional",
    creativity_tone_label: creativityToneLabel,
    intent: (intent || "").trim(),
  };
}
