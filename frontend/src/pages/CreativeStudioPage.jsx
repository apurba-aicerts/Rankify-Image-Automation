import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AiAssistantGlyph } from "../components/AiAssistantGlyph.jsx";
import { useApp } from "../context/AppContext.jsx";
import { buildStudioCampaignPayload } from "../lib/campaignAssembler.js";
import {
  CAMPAIGN_GOALS,
  PROMPT_ASSIST_SNIPPETS,
  STUDIO_PLATFORMS,
  STUDIO_VOICE_TONES,
  creativityBiasShort,
  toneLabelFromBias,
} from "../lib/campaignGoals.js";
import { enforcementFromBrand } from "../lib/brandEnforcementPreview.js";
import {
  buildCaptionHashtagDraft,
} from "../lib/creativeDirectionPreview.js";
import { toastComingSoon } from "../lib/featureMessages.js";
import { modelOptionLabel, modelSupportsImageSize } from "../lib/modelCatalog.js";
import "../styles/studio.css";

function aspectRatioToCss(r) {
  if (!r || r === "1:1") return "1 / 1";
  const parts = String(r).split(":");
  if (parts.length === 2) {
    const a = Number(parts[0]);
    const b = Number(parts[1]);
    if (a > 0 && b > 0) return `${a} / ${b}`;
  }
  return "1 / 1";
}

function parseHashtagLine(line) {
  return (line || "")
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => t.startsWith("#"));
}

export function CreativeStudioPage() {
  const { brandId: rawParam } = useParams();
  const brandId = rawParam ? decodeURIComponent(rawParam) : "";
  const navigate = useNavigate();
  const { client, showToast, apiBase, apiKey } = useApp();
  const studioEditAiGradId = `studio-edit-ai-${useId().replace(/:/g, "")}`;

  const [brand, setBrand] = useState(null);
  const [logoOk, setLogoOk] = useState(false);
  const [brandLogoSrc, setBrandLogoSrc] = useState(null);
  const [modelCatalog, setModelCatalog] = useState([]);
  const [ratios, setRatios] = useState([]);
  const [sizes, setSizes] = useState([]);
  const [modelName, setModelName] = useState("gemini-3-pro-image-preview");
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [imageSize, setImageSize] = useState("2K");
  const [numImages, setNumImages] = useState(1);

  const [campaignGoal, setCampaignGoal] = useState("brand_awareness");
  const [voiceToneId, setVoiceToneId] = useState("professional");
  const [platforms, setPlatforms] = useState(["linkedin"]);
  const [toneBias, setToneBias] = useState(50);
  const [intent, setIntent] = useState("");

  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [captionText, setCaptionText] = useState("");
  const [hashtagChips, setHashtagChips] = useState([]);
  const [pinnedPreviewUrl, setPinnedPreviewUrl] = useState(null);
  const [artifactHistory, setArtifactHistory] = useState([]);
  const [aiEditHint, setAiEditHint] = useState("");
  const [refFile, setRefFile] = useState(null);
  const [refObjectUrl, setRefObjectUrl] = useState(null);
  const [editBusy, setEditBusy] = useState(false);
  const [activeSourceFilename, setActiveSourceFilename] = useState(null);
  const aiEditInputRef = useRef(null);

  const toneLabel = useMemo(() => toneLabelFromBias(toneBias), [toneBias]);
  const creativityShort = useMemo(() => creativityBiasShort(toneBias), [toneBias]);
  const voiceToneLabel = useMemo(
    () => STUDIO_VOICE_TONES.find((t) => t.id === voiceToneId)?.label || "Professional",
    [voiceToneId]
  );

  /** Versions = current studio session only (this generate run + edits), not full gallery history. */
  const toVersionItems = (images) =>
    (images || [])
      .map((img, idx) => ({
        id: `v-${img.filename || idx}`,
        url: img.url,
        filename: img.filename,
      }))
      .filter((x) => x.url && x.filename);

  const setSessionVersionsFromImages = useCallback((images) => {
    setArtifactHistory(toVersionItems(images).slice(0, 16));
  }, []);

  const appendSessionVersions = useCallback((images) => {
    const newItems = toVersionItems(images);
    if (!newItems.length) return;
    setArtifactHistory((h) => {
      const seen = new Set(h.map((x) => x.filename));
      const merged = [...newItems.filter((x) => !seen.has(x.filename)), ...h];
      return merged.slice(0, 16);
    });
  }, []);

  const fetchAndApplySocialCopy = useCallback(
    async (imageFilename) => {
      if (!brandId || !brand || !imageFilename) return;
      const studio_campaign = buildStudioCampaignPayload({
        campaignGoalId: campaignGoal,
        platforms,
        voiceToneLabel,
        creativityToneLabel: toneLabel,
        intent,
      });
      try {
        const copyData = await client.request(
          `/api/brands/${encodeURIComponent(brandId)}/text/social-copy`,
          { method: "POST", json: { studio_campaign, image_filename: imageFilename } },
        );
        setCaptionText(copyData.caption);
        setHashtagChips(parseHashtagLine(copyData.hashtags));
      } catch (e) {
        const cap = buildCaptionHashtagDraft({
          displayName: brand.display_name || brandId,
          intent,
          goalLabel: CAMPAIGN_GOALS.find((g) => g.id === campaignGoal)?.label || "Campaign",
          platforms,
        });
        setCaptionText(cap.caption);
        setHashtagChips(parseHashtagLine(cap.hashtags));
        showToast(e.message || String(e), "error");
      }
    },
    [
      brand,
      brandId,
      campaignGoal,
      client,
      intent,
      platforms,
      showToast,
      toneLabel,
      voiceToneLabel,
    ],
  );

  const enforcement = useMemo(() => {
    const base = enforcementFromBrand(brand);
    return { ...base, logo: logoOk };
  }, [brand, logoOk]);

  const ratioOptions = useMemo(() => {
    const preferred = ["1:1", "4:5", "9:16", "16:9"];
    const fromApi = (ratios || []).filter(Boolean);
    const merged = [...new Set([...preferred, ...fromApi])];
    return preferred.filter((r) => merged.includes(r));
  }, [ratios]);

  const hasGeneratedImage = Boolean(result?.images?.length);
  const primaryUrl = result?.images?.[0]?.url;
  const displayUrl = pinnedPreviewUrl ?? primaryUrl;
  const primaryPlatformLabel =
    STUDIO_PLATFORMS.find((p) => p.id === platforms[0])?.label || "Social";

  const load = useCallback(async () => {
    if (!brandId) return;
    try {
      const [b, meta, mlist] = await Promise.all([
        client.request(`/api/brands/${encodeURIComponent(brandId)}`),
        client.request("/api/image-sizes"),
        client.request("/api/models"),
      ]);
      setBrand(b);
      setAspectRatio(b.social_defaults?.default_aspect_ratio || "1:1");
      const defSize = b.social_defaults?.default_image_size;
      setImageSize(defSize && ["1K", "2K", "4K"].includes(defSize) ? defSize : "2K");
      setRatios(meta.aspect_ratios || []);
      setSizes(meta.image_sizes || []);
      const catalog = (mlist.models || []).filter((m) => m.model_name);
      setModelCatalog(catalog);
      const ids = catalog.map((m) => m.model_name);
      setModelName((prev) => (ids.length && !ids.includes(prev) ? ids[0] : prev));

      const pref = (b.social_defaults?.preferred_platforms || []).map((p) => String(p).toLowerCase());
      if (pref.length) setPlatforms(pref);

      let hasLogo = false;
      try {
        const url = await client.fetchBrandLogoObjectUrl(brandId);
        if (url) {
          hasLogo = true;
          setBrandLogoSrc(url);
        } else {
          setBrandLogoSrc(null);
        }
      } catch {
        hasLogo = false;
        setBrandLogoSrc(null);
      }
      setLogoOk(hasLogo);
    } catch (e) {
      showToast(e.message || String(e), "error");
      navigate("/", { replace: true });
    }
  }, [brandId, client, navigate, showToast]);

  useEffect(() => {
    load();
  }, [load]);

  /** New brand or revisit studio: empty versions until this session generates. */
  useEffect(() => {
    setArtifactHistory([]);
    setResult(null);
    setPinnedPreviewUrl(null);
    setActiveSourceFilename(null);
    setCaptionText("");
    setHashtagChips([]);
  }, [brandId]);

  useEffect(() => {
    return () => {
      if (brandLogoSrc) URL.revokeObjectURL(brandLogoSrc);
    };
  }, [brandLogoSrc]);

  useEffect(() => {
    return () => {
      if (refObjectUrl) URL.revokeObjectURL(refObjectUrl);
    };
  }, [refObjectUrl]);

  function togglePlatform(id) {
    setPlatforms((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
  }

  function insertSnippet(text) {
    setIntent((prev) => `${prev || ""}${text}`);
  }

  function onReferenceFile(ev) {
    const file = ev.target.files?.[0];
    if (!file) return;
    if (refObjectUrl) URL.revokeObjectURL(refObjectUrl);
    setRefFile(file);
    setRefObjectUrl(URL.createObjectURL(file));
    ev.target.value = "";
  }

  function clearReference(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    if (refObjectUrl) URL.revokeObjectURL(refObjectUrl);
    setRefFile(null);
    setRefObjectUrl(null);
  }

  async function runCampaign() {
    if (!brandId || !brand) return;
    if (!(intent || "").trim()) {
      showToast("Add a short prompt—what should this visual communicate?", "error");
      return;
    }
    setBusy(true);
    setResult(null);
    setArtifactHistory([]);
    setCaptionText("");
    setHashtagChips([]);
    setPinnedPreviewUrl(null);
    setActiveSourceFilename(null);
    try {
      const studioCampaign = buildStudioCampaignPayload({
        campaignGoalId: campaignGoal,
        platforms,
        voiceToneLabel,
        creativityToneLabel: toneLabel,
        intent,
      });
      let data;
      if (refFile) {
        const fd = new FormData();
        fd.append("brand_id", brandId);
        fd.append("studio_campaign", JSON.stringify(studioCampaign));
        fd.append("model_name", modelName);
        fd.append("num_images", String(numImages));
        fd.append("aspect_ratio", aspectRatio);
        if (modelSupportsImageSize(modelCatalog, modelName)) {
          fd.append("image_size", imageSize);
        }
        fd.append("reference_image", refFile);
        const base = apiBase.replace(/\/+$/, "");
        if (!apiKey) throw new Error("Configure your API key in Settings.");
        const res = await fetch(`${base}/api/generate-with-reference`, {
          method: "POST",
          headers: { "x-api-key": apiKey },
          body: fd,
        });
        const text = await res.text();
        let parsed = null;
        try {
          parsed = text ? JSON.parse(text) : null;
        } catch {
          parsed = text;
        }
        if (!res.ok) {
          const msg =
            parsed && typeof parsed === "object" && "detail" in parsed
              ? JSON.stringify(parsed.detail)
              : text || res.statusText;
          throw new Error(`${res.status}: ${msg}`);
        }
        data = parsed;
      } else {
        data = await client.request("/api/generate", {
          method: "POST",
          json: {
            brand_id: brandId,
            studio_campaign: studioCampaign,
            model_name: modelName,
            num_images: numImages,
            aspect_ratio: aspectRatio,
            image_size: modelSupportsImageSize(modelCatalog, modelName) ? imageSize : undefined,
          },
        });
      }
      const images = data.images || [];
      setResult(data);
      setSessionVersionsFromImages(images);
      const primaryFn = images[0]?.filename ?? null;
      setActiveSourceFilename(primaryFn);
      void fetchAndApplySocialCopy(primaryFn);
      showToast(images.length > 1 ? `Generated ${images.length} variants.` : "Visual generated.");
    } catch (e) {
      showToast(e.message || String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  function stubEditWithAi() {
    if (!displayUrl) return;
    aiEditInputRef.current?.focus();
    aiEditInputRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function stubRegenerate() {
    if (!displayUrl) return;
    toastComingSoon(showToast, "Regenerate");
  }

  function duplicateCurrent() {
    if (!displayUrl) return;
    const fromHistory = artifactHistory.find((a) => a.url === displayUrl);
    const fn =
      fromHistory?.filename ??
      (displayUrl === primaryUrl ? result?.images?.[0]?.filename : null) ??
      activeSourceFilename;
    setArtifactHistory((h) => [{ id: `dup-${Date.now()}`, url: displayUrl, filename: fn }, ...h].slice(0, 16));
    showToast("Duplicate saved to versions.");
  }

  async function submitAiEditBar() {
    const t = (aiEditHint || "").trim();
    if (!t) {
      showToast("Describe the change you want (e.g. darker background).", "error");
      return;
    }
    if (!displayUrl) {
      showToast("Generate a visual first, then use AI edit.", "error");
      return;
    }
    if (!brandId) {
      showToast("Missing brand.", "error");
      return;
    }
    setEditBusy(true);
    try {
      const editBody = {
        source_filename: activeSourceFilename,
        instruction: t,
        model_name: modelName,
        aspect_ratio: aspectRatio,
      };
      if (modelSupportsImageSize(modelCatalog, modelName)) {
        editBody.image_size = imageSize;
      }
      const data = await client.request(`/api/brands/${encodeURIComponent(brandId)}/gallery/edit`, {
        method: "POST",
        json: editBody,
      });
      setResult(data);
      setPinnedPreviewUrl(null);
      const editImages = data.images || [];
      const fn = editImages[0]?.filename;
      if (fn) setActiveSourceFilename(fn);
      appendSessionVersions(editImages);
      void fetchAndApplySocialCopy(fn);
      setAiEditHint("");
      showToast("Edit applied.");
    } catch (e) {
      showToast(e.message || String(e), "error");
    } finally {
      setEditBusy(false);
    }
  }

  const displayName = brand?.display_name || brandId || "Brand";
  const brandInitials = (displayName || "B")
    .replace(/[^a-zA-Z0-9]/g, "")
    .slice(0, 2)
    .toUpperCase() || "BR";

  const paletteSwatches = useMemo(() => {
    const prim = (brand?.colors?.primary || []).filter(Boolean);
    const sec = (brand?.colors?.secondary || []).filter(Boolean);
    return [...prim, ...sec].slice(0, 8);
  }, [brand]);

  const fontLine = [brand?.typography?.headline_font, brand?.typography?.body_font].filter(Boolean).join(" / ") || "—";

  return (
    <div className="studio-os">
      <header className="studio-os__header">
        <div className="studio-os__header-row">
          <Link to="/" className="studio-os__back">
            ← Workspaces
          </Link>
          <div className="studio-os__brand-line">
            <span className="studio-os__kicker">AI Creative Studio</span>
            <h1 className="studio-os__title">Generating for: {displayName}</h1>
          </div>
          <Link className="btn btn-secondary btn-sm studio-os__gallery" to={`/brands/${encodeURIComponent(brandId)}/gallery`}>
            Gallery
          </Link>
        </div>
      </header>

      <div className="studio-os__grid">
        {/* —— Left: campaign controls —— */}
        <aside className="studio-os__col studio-os__col--left">
          <label className="os-field">
            <span className="os-label">Prompt</span>
            <textarea
              className="os-textarea os-textarea--prompt"
              rows={7}
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder="Announce our new AI Engineering certification — futuristic, professional, with a confident hero statement and CTA."
            />
          </label>

          <div className="os-field">
            <span className="os-label">Prompt assistant</span>
            <div className="os-chips">
              {PROMPT_ASSIST_SNIPPETS.map((s) => (
                <button key={s.label} type="button" className="os-chip" onClick={() => insertSnippet(s.text)}>
                  + {s.chip || s.label}
                </button>
              ))}
            </div>
          </div>

          <label className="os-field">
            <span className="os-label">Campaign objective</span>
            <select className="os-select" value={campaignGoal} onChange={(e) => setCampaignGoal(e.target.value)}>
              {CAMPAIGN_GOALS.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.label}
                </option>
              ))}
            </select>
          </label>

          <div className="os-field">
            <span className="os-label">Platform</span>
            <div className="os-chips os-chips--platform">
              {STUDIO_PLATFORMS.filter((p) => ["linkedin", "instagram", "x", "facebook", "threads"].includes(p.id)).map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={`os-chip os-chip--toggle ${platforms.includes(p.id) ? "on" : ""}`}
                  onClick={() => togglePlatform(p.id)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="os-field">
            <span className="os-label">Ratio</span>
            <div className="os-segment" role="group" aria-label="Aspect ratio">
              {ratioOptions.map((r) => (
                <button
                  key={r}
                  type="button"
                  className={aspectRatio === r ? "on" : ""}
                  onClick={() => setAspectRatio(r)}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          <label className="os-field">
            <span className="os-label">Tone</span>
            <select className="os-select" value={voiceToneId} onChange={(e) => setVoiceToneId(e.target.value)}>
              {STUDIO_VOICE_TONES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          <div className="os-field">
            <div className="os-slider-head">
              <span className="os-label">AI creativity</span>
              <span className="os-slider-value">{creativityShort}</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={toneBias}
              onChange={(e) => setToneBias(Number(e.target.value))}
              className="os-range"
            />
            <div className="os-slider-ticks">
              <span>Faithful</span>
              <span>Balanced</span>
              <span>Wild</span>
            </div>
          </div>

          <div className="os-field os-field--row">
            <label className="os-inline">
              <span className="os-label">Model</span>
              <select className="os-select" value={modelName} onChange={(e) => setModelName(e.target.value)}>
                {modelCatalog.map((m) => (
                  <option key={m.model_name} value={m.model_name}>
                    {modelOptionLabel(m)}
                  </option>
                ))}
              </select>
            </label>
            <label className="os-inline">
              <span className="os-label">Variants</span>
              <select className="os-select" value={numImages} onChange={(e) => setNumImages(Number(e.target.value))}>
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            {modelSupportsImageSize(modelCatalog, modelName) && (
              <label className="os-inline">
                <span className="os-label">Size</span>
                <select className="os-select" value={imageSize} onChange={(e) => setImageSize(e.target.value)}>
                  {(sizes.length ? sizes : ["1K", "2K", "4K"]).map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          <label className="os-dropzone">
            <input type="file" accept="image/*" className="os-dropzone-input" onChange={onReferenceFile} />
            {refObjectUrl ? (
              <>
                <img src={refObjectUrl} alt="Reference preview" className="os-dropzone-preview" />
                <button type="button" className="os-dropzone-clear" onClick={clearReference}>
                  Remove
                </button>
              </>
            ) : (
              <span className="os-dropzone-text">Upload reference image (optional)</span>
            )}
          </label>

          <button type="button" className="os-generate" onClick={runCampaign} disabled={busy || editBusy || !brandId}>
            {busy ? "Generating…" : "Generate"}
          </button>
        </aside>

        {/* —— Center: preview + tools —— */}
        <section className="studio-os__col studio-os__col--center">
          <div className="os-preview-wrap">
            <div
              className="os-preview-card"
              style={{ aspectRatio: aspectRatioToCss(aspectRatio) }}
            >
              <div className="os-preview-card__badges">
                <span className="os-preview-badge os-preview-badge--brand">{brandInitials}</span>
                <span className="os-preview-badge os-preview-badge--plat">{primaryPlatformLabel}</span>
              </div>
              {displayUrl ? (
                <a className="os-preview-imglink" href={displayUrl} target="_blank" rel="noreferrer">
                  <img src={displayUrl} alt="Generated visual" className="os-preview-img" />
                </a>
              ) : (
                <div className="os-preview-placeholder">
                  <p>Your generated visual appears here</p>
                  <span>1:1 · {primaryPlatformLabel} · {voiceToneLabel}</span>
                </div>
              )}
            </div>
          </div>

          <div className="os-toolbar">
            <button type="button" className="os-tool os-tool--withGlyph" disabled={!displayUrl || editBusy} onClick={stubEditWithAi}>
              <span className="os-tool-glyph" aria-hidden>
                <AiAssistantGlyph gradId={studioEditAiGradId} size={18} className="ai-onboard-glyph" />
              </span>
              Edit with AI
            </button>
            <button type="button" className="os-tool" disabled={!displayUrl} onClick={stubRegenerate}>
              <span className="os-tool-ic" aria-hidden>
                ↻
              </span>
              Regenerate
            </button>
            <button type="button" className="os-tool" disabled={!displayUrl} onClick={duplicateCurrent}>
              <span className="os-tool-ic" aria-hidden>
                ⧉
              </span>
              Duplicate
            </button>
            {displayUrl ? (
              <a className="os-tool os-tool--link" href={displayUrl} download target="_blank" rel="noreferrer">
                <span className="os-tool-ic" aria-hidden>
                  ⬇
                </span>
                Download
              </a>
            ) : (
              <button type="button" className="os-tool" disabled>
                <span className="os-tool-ic" aria-hidden>
                  ⬇
                </span>
                Download
              </button>
            )}
          </div>

          <div className="os-ai-bar">
            <input
              ref={aiEditInputRef}
              type="text"
              className="os-ai-bar-input"
              value={aiEditHint}
              onChange={(e) => setAiEditHint(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !editBusy && submitAiEditBar()}
              placeholder="Try: 'Slightly darker background only' — uses the Model selected at left (Flash or Pro)"
              disabled={!displayUrl || busy || editBusy}
            />
            <button
              type="button"
              className="os-ai-bar-send"
              onClick={submitAiEditBar}
              disabled={!displayUrl || busy || editBusy}
              title="Send"
            >
              {editBusy ? "…" : "➤"}
            </button>
          </div>
        </section>

        {/* —— Right: brand + caption + versions —— */}
        <aside className="studio-os__col studio-os__col--right">
          <div className="os-brand-card">
            <div className="os-brand-card__head">
              {brandLogoSrc ? (
                <img src={brandLogoSrc} alt="" className="os-brand-logo" />
              ) : (
                <div className="os-brand-logo os-brand-logo--ph">{brandInitials}</div>
              )}
              <div>
                <p className="os-brand-name">{displayName}</p>
                <p className="os-brand-fonts">{fontLine}</p>
              </div>
            </div>
            <div className="os-palette">
              <span className="os-label">Palette</span>
              <div className="os-palette-swatches">
                {paletteSwatches.length ? (
                  paletteSwatches.map((hex) => (
                    <span key={hex} className="os-swatch" style={{ background: hex }} title={hex} />
                  ))
                ) : (
                  <span className="os-muted">Add colors in brand profile</span>
                )}
              </div>
            </div>
            <ul className="os-brand-checks">
              <li className={enforcement.logo ? "ok" : ""}>{enforcement.logo ? "✓" : "○"} Logo locked</li>
              <li className={enforcement.typography ? "ok" : ""}>{enforcement.typography ? "✓" : "○"} Brand fonts</li>
              <li className={enforcement.palette ? "ok" : ""}>{enforcement.palette ? "✓" : "○"} Palette enforced</li>
            </ul>
          </div>

          <div className="os-caption-block">
            <label className="os-field">
              <span className="os-label">Caption</span>
              <textarea
                className="os-textarea os-textarea--caption"
                rows={12}
                value={captionText}
                onChange={(e) => setCaptionText(e.target.value)}
                placeholder={hasGeneratedImage ? "" : "Caption appears after you generate."}
                disabled={!hasGeneratedImage}
              />
            </label>
            <div className="os-field">
              <span className="os-label">Hashtags</span>
              <div className="os-hash-row">
                {hashtagChips.length ? (
                  hashtagChips.map((tag) => (
                    <span key={tag} className="os-hash-chip">
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="os-muted"># tags appear after generation</span>
                )}
              </div>
            </div>
          </div>

          <div className="os-versions">
            <h2 className="os-side-title">Versions</h2>
            {artifactHistory.length ? (
              <div className="os-version-strip">
                {artifactHistory.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    className={`os-version-thumb ${displayUrl === a.url ? "active" : ""}`}
                    onClick={() => {
                      const isPrimary = a.url === primaryUrl;
                      setPinnedPreviewUrl(isPrimary ? null : a.url);
                      const fn = a.filename ?? (isPrimary ? result?.images?.[0]?.filename : null);
                      if (fn) setActiveSourceFilename(fn);
                    }}
                  >
                    <img src={a.url} alt="" />
                  </button>
                ))}
              </div>
            ) : (
              <p className="os-muted">Variants from this session appear here. Full history is in Gallery.</p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
