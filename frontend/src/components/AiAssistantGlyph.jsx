/** Decorative “AI” mark (not a brand logo). Unique `gradId` per instance for SVG defs. */
export function AiAssistantGlyph({ gradId, size = 40, className = "ai-onboard-glyph" }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#a78bfa" />
          <stop offset="55%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
      <circle cx="20" cy="20" r="14" fill={`url(#${gradId})`} opacity="0.22" />
      <circle cx="20" cy="20" r="6.5" fill={`url(#${gradId})`} opacity="0.55" />
      <path
        d="M20 4v6M20 30v6M4 20h6M30 20h6M8.5 8.5l4.2 4.2M27.3 27.3l4.2 4.2M8.5 31.5l4.2-4.2M27.3 12.7l4.2-4.2"
        stroke={`url(#${gradId})`}
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.85"
      />
    </svg>
  );
}
