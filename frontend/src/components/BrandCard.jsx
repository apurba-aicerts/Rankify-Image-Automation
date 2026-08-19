import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../context/AppContext.jsx";
import { PlatformChips } from "./PlatformChips.jsx";

function typographyPreview(t) {
  if (!t) return "System UI";
  const h = (t.headline_font || t.primary_font || "").trim();
  const b = (t.body_font || t.primary_font || "").trim();
  const parts = [];
  if (h) parts.push(h);
  if (b && b !== h) parts.push(b);
  return parts.length ? parts.join(" · ") : "System UI";
}

function professionalTagline(detail) {
  if (!detail) return "Loading workspace…";
  const t = (detail.tagline || "").trim();
  if (t) return t;
  const cats = (detail.content_themes?.categories || []).filter(Boolean);
  if (cats.length) return cats.slice(0, 3).join(" · ");
  const themes = (detail.content_themes?.recurring_themes || []).filter(Boolean);
  if (themes.length) return themes.slice(0, 2).join(" · ");
  const tone = (detail.voice?.tone_keywords || []).slice(0, 3).join(" · ");
  if (tone) return tone;
  return "Multi-channel content studio";
}

function deriveStatus({ statsLoading, detail, total }) {
  if (statsLoading) return { label: "Syncing", variant: "syncing" };
  if (!detail) return { label: "Syncing", variant: "syncing" };
  if (total === 0) return { label: "Draft", variant: "draft" };
  return { label: "Active", variant: "active" };
}

export function BrandCard({
  summary,
  detail,
  stats,
  statsLoading,
  onEdit,
  onDelete,
}) {
  const { client, showToast } = useApp();
  const navigate = useNavigate();
  const [thumbUrl, setThumbUrl] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef(null);

  const total = stats?.total ?? 0;
  const thisWeek = stats?.thisWeek ?? 0;
  const status = deriveStatus({ statsLoading, detail, total });
  const platforms = detail?.social_defaults?.preferred_platforms || [];

  useEffect(() => {
    let objectUrl = null;
    let cancelled = false;
    (async () => {
      try {
        const url = await client.fetchBrandLogoObjectUrl(summary.brand_id);
        if (!cancelled) setThumbUrl(url);
        objectUrl = url;
      } catch {
        if (!cancelled) setThumbUrl(null);
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [client, summary.brand_id]);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  const prim = detail?.colors?.primary?.filter(Boolean) || [];
  const accent = prim[0] || "#6ea8fe";
  const accent2 = prim[1] || "#334155";
  const gradient = `linear-gradient(145deg, ${accent} 0%, ${accent2} 55%, #0f1419 100%)`;
  const glow = `0 0 0 1px rgba(255,255,255,0.06), 0 20px 50px -12px ${accent}33`;

  const typo = typographyPreview(detail?.typography);
  const tagline = professionalTagline(detail);
  const channels = platforms.length || 0;

  async function copyWorkspaceId() {
    try {
      await navigator.clipboard.writeText(summary.brand_id);
      showToast("Workspace ID copied.");
    } catch {
      showToast("Could not copy ID.", "error");
    }
    setMenuOpen(false);
  }

  return (
    <article ref={rootRef} className="bcard" style={{ boxShadow: glow }}>
      <div className="bcard__hero" style={{ background: gradient }}>
        <div className="bcard__heroNoise" aria-hidden />
        <span className={`bcard__status bcard__status--${status.variant}`}>{status.label}</span>
        <div className="bcard__logoRing">
          <div className="bcard__logoInner">
            {thumbUrl ? (
              <img src={thumbUrl} alt="" className="bcard__logoImg" />
            ) : (
              <span className="bcard__logoInitials" aria-hidden>
                {summary.display_name?.replace(/\s+/g, "").slice(0, 2).toUpperCase() || "?"}
              </span>
            )}
          </div>
        </div>
        <PlatformChips platforms={platforms} />
      </div>

      <div className="bcard__body">
        <div className="bcard__titleRow">
          <div>
            <h2 className="bcard__name">{summary.display_name}</h2>
            <p className="bcard__tagline">{tagline}</p>
          </div>
          <div className="bcard__menuWrap">
            <button
              type="button"
              className="bcard__menuBtn"
              aria-expanded={menuOpen}
              aria-haspopup="true"
              aria-label="More actions"
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen((o) => !o);
              }}
            >
              <span className="bcard__menuDots" />
            </button>
            {menuOpen && (
              <div className="bcard__menu" role="menu">
                <button type="button" role="menuitem" className="bcard__menuItem" onClick={() => { setMenuOpen(false); onEdit(summary.brand_id); }}>
                  Edit brand
                </button>
                <button type="button" role="menuitem" className="bcard__menuItem bcard__menuItem--muted" onClick={copyWorkspaceId}>
                  Copy workspace ID
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="bcard__menuItem bcard__menuItem--danger"
                  onClick={() => {
                    setMenuOpen(false);
                    onDelete(summary.brand_id, summary.display_name);
                  }}
                >
                  Delete workspace
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="bcard__typeRow" title="Typography from brand profile">
          <span className="bcard__typeLabel">Type</span>
          <span className="bcard__typeValue">{typo}</span>
        </div>

        <div className="bcard__metrics">
          <div className="bcard__metric">
            <span className="bcard__metricNum">{statsLoading ? "—" : total}</span>
            <span className="bcard__metricLbl">Posts</span>
          </div>
          <div className="bcard__metric">
            <span className="bcard__metricNum">{statsLoading ? "—" : thisWeek}</span>
            <span className="bcard__metricLbl">7-day</span>
          </div>
          <div className="bcard__metric">
            <span className="bcard__metricNum">{statsLoading ? "—" : channels}</span>
            <span className="bcard__metricLbl">Channels</span>
          </div>
        </div>

        {!statsLoading && total > 0 && (
          <p className="bcard__pulse">
            {thisWeek > 0
              ? `${((thisWeek / total) * 100).toFixed(1)}% of assets refreshed in the last 7 days`
              : "No new assets in the last 7 days"}
          </p>
        )}

        <div className="bcard__footer">
          <button
            type="button"
            className="bcard__generate"
            onClick={() => navigate(`/brands/${encodeURIComponent(summary.brand_id)}/studio`)}
          >
            Generate campaign
          </button>
        </div>
      </div>
    </article>
  );
}

export function CreateBrandCard({ onClick }) {
  return (
    <button type="button" className="bcard bcard--create" onClick={onClick}>
      <div className="bcard__createGlow" aria-hidden />
      <div className="bcard__createInner">
        <span className="bcard__createIcon" aria-hidden>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 5v14M5 12h14" strokeLinecap="round" />
          </svg>
        </span>
        <span className="bcard__createTitle">New workspace</span>
        <span className="bcard__createSub">Guided brand onboarding</span>
      </div>
    </button>
  );
}
