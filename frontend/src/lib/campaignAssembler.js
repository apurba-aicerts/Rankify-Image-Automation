/**
 * Build the `studio_campaign` object for POST /api/generate.
 * TITLE / SUBTITLE / BODY / CTA assembly runs on the server (`generation.campaign_assembler`).
 */
export function buildStudioCampaignPayload({
  campaignGoalId,
  platforms,
  voiceToneLabel,
  creativityToneLabel,
  intent,
}) {
  return {
    campaign_goal_id: campaignGoalId,
    platforms: (platforms || []).filter(Boolean).map((p) => String(p).toLowerCase()),
    voice_tone_label: (voiceToneLabel || "Professional").trim() || "Professional",
    creativity_tone_label: creativityToneLabel,
    intent: (intent || "").trim(),
  };
}
