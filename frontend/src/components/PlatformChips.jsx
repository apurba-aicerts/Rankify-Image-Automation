/**
 * Compact platform marks for brand cards (normalized ids: linkedin, instagram, x, etc.)
 */

const ICONS = {
  linkedin: (
    <svg viewBox="0 0 24 24" aria-hidden>
      <title>LinkedIn</title>
      <path
        fill="currentColor"
        d="M6.5 8.77v12.5H2.15V8.77H6.5zM4.35 3.15c1.4 0 2.28.93 2.28 2.1 0 1.16-.88 2.1-2.28 2.1-1.42 0-2.3-.94-2.3-2.1 0-1.17.88-2.1 2.3-2.1zM22.85 21.27h-4.33v-6.04c0-1.52-.54-2.56-1.9-2.56-1.04 0-1.66.7-1.93 1.38-.1.24-.12.58-.12.92v6.3H10.24s.06-10.22 0-11.27h4.33v1.6c.58-.9 1.6-1.48 2.92-1.48 2.13 0 3.73 1.4 3.73 4.4v6.75z"
      />
    </svg>
  ),
  instagram: (
    <svg viewBox="0 0 24 24" aria-hidden>
      <title>Instagram</title>
      <path
        fill="currentColor"
        d="M7.8 2h8.4A5.8 5.8 0 0122 7.8v8.4a5.8 5.8 0 01-5.8 5.8H7.8A5.8 5.8 0 012 16.2V7.8A5.8 5.8 0 017.8 2zm-.2 2A3.8 3.8 0 004 7.8v8.4A3.8 3.8 0 007.8 20h8.4a3.8 3.8 0 003.8-3.8V7.8A3.8 3.8 0 0016.2 4H7.6zm8.7 1.5a1 1 0 110 2 1 1 0 010-2zM12 7a5 5 0 110 10 5 5 0 010-10zm0 2a3 3 0 100 6 3 3 0 000-6z"
      />
    </svg>
  ),
  x: (
    <svg viewBox="0 0 24 24" aria-hidden>
      <title>X</title>
      <path
        fill="currentColor"
        d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"
      />
    </svg>
  ),
  twitter: (
    <svg viewBox="0 0 24 24" aria-hidden>
      <title>Twitter</title>
      <path
        fill="currentColor"
        d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"
      />
    </svg>
  ),
  facebook: (
    <svg viewBox="0 0 24 24" aria-hidden>
      <title>Facebook</title>
      <path
        fill="currentColor"
        d="M13.5 22v-8.2h2.8l.4-3.2H13.5V8.5c0-.9.3-1.5 1.6-1.5h1.7V4.1c-.3 0-1.3-.1-2.5-.1-2.5 0-4.2 1.5-4.2 4.3v2.4H7v3.2h2.1V22h4.4z"
      />
    </svg>
  ),
  tiktok: (
    <svg viewBox="0 0 24 24" aria-hidden>
      <title>TikTok</title>
      <path
        fill="currentColor"
        d="M16.6 5.82s.51.5 1.3.5c.8 0 1.4-.66 1.4-1.48V2h-2.2v7.2c-.2.22-.5.36-.9.36-.5 0-.9-.4-.9-.9V2h-2.2v6.66c0 1.8 1.5 3.26 3.3 3.26.3 0 .6 0 .9-.1v2.1c-.5.15-1 .23-1.6.23-2.8 0-5-2.26-5-5.04V2H8v12.5c0 3.3 2.7 6 6 6s6-2.7 6-6V9.9c-1.1.7-2.4 1.1-3.8 1.1-1.2 0-2.3-.3-3.2-.9v-4.3z"
      />
    </svg>
  ),
  youtube: (
    <svg viewBox="0 0 24 24" aria-hidden>
      <title>YouTube</title>
      <path
        fill="currentColor"
        d="M21.8 8.001a2.75 2.75 0 00-1.94-1.955C18.12 5.7 12 5.7 12 5.7s-6.12 0-7.86.326A2.75 2.75 0 002.2 8.002C2 9.87 2 12 2 12s0 2.13.2 3.999c.23 1.07 1.04 1.8 1.94 1.955 1.74.326 7.86.326 7.86.326s6.12 0 7.86-.326a2.75 2.75 0 001.94-1.955C22 14.13 22 12 22 12s0-2.13-.2-3.999zM10 15.5v-7l6 3.5-6 3.5z"
      />
    </svg>
  ),
};

function normalizePlatform(p) {
  const s = String(p || "")
    .trim()
    .toLowerCase();
  if (s === "twitter") return "x";
  return s;
}

export function PlatformChips({ platforms }) {
  const list = [...new Set((platforms || []).map(normalizePlatform).filter(Boolean))];
  if (!list.length) {
    return <span className="bcard-platforms bcard-platforms--empty">Channels</span>;
  }
  return (
    <ul className="bcard-platforms" aria-label="Connected platforms">
      {list.map((id) => {
        const node = ICONS[id];
        if (!node) {
          return (
            <li key={id} className="bcard-platform bcard-platform--generic" title={id}>
              <span>{id.slice(0, 2)}</span>
            </li>
          );
        }
        return (
          <li key={id} className="bcard-platform" title={id}>
            {node}
          </li>
        );
      })}
    </ul>
  );
}
