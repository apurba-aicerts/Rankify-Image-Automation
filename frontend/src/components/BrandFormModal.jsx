import { useEffect, useId, useRef, useState } from "react";
import { AiAssistantGlyph } from "./AiAssistantGlyph.jsx";
import { Modal } from "./Modal.jsx";
import { useApp } from "../context/AppContext.jsx";
import "../styles/studio.css";
import {
  brandToForm,
  buildBrandCreatePayload,
  buildBrandPutConfiguration,
  draftPayloadToForm,
  emptyBrandForm,
} from "../lib/brandForm.js";

/** Default OpenAI model for brand onboarding draft (no UI picker). */
const BRAND_AI_DRAFT_MODEL = "gpt-4o-2024-08-06";

async function uploadLogoFile({ apiBase, apiKey, brandId, file }) {
  const base = apiBase.replace(/\/+$/, "");
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${base}/api/brands/${encodeURIComponent(brandId)}/assets/logo`, {
    method: "POST",
    headers: { "x-api-key": apiKey },
    body: fd,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(text || res.statusText);
}

export function BrandFormModal({ open, mode, brandId, onClose, onSaved }) {
  const { client, showToast, loadBrands, apiBase, apiKey } = useApp();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(() => emptyBrandForm());
  const [logoFile, setLogoFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [aiMaterials, setAiMaterials] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiOnboardNoticeVisible, setAiOnboardNoticeVisible] = useState(false);
  const aiDetailsRef = useRef(null);
  const aiGlyphGradId = `ai-onboard-grad-${useId().replace(/:/g, "")}`;
  const aiSummaryGlyphGradId = `ai-onboard-summary-grad-${useId().replace(/:/g, "")}`;

  useEffect(() => {
    if (!open) return;
    setStep(0);
    setLogoFile(null);
    setAiOnboardNoticeVisible(false);
    if (mode === "create") {
      setForm(emptyBrandForm());
      setAiMaterials("");
      return;
    }
    if (mode === "edit" && brandId) {
      setLoading(true);
      client
        .request(`/api/brands/${encodeURIComponent(brandId)}`)
        .then((b) => setForm(brandToForm(b)))
        .catch((e) => showToast(e.message || String(e), "error"))
        .finally(() => setLoading(false));
    }
  }, [open, mode, brandId, client, showToast]);

  function setF(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function runAiDraft() {
    const mat = (aiMaterials || "").trim();
    if (mat.length < 30) {
      showToast("Paste at least 30 characters of brand material.", "error");
      return;
    }
    setAiBusy(true);
    try {
      const data = await client.request("/api/brands/ai-draft", {
        method: "POST",
        json: {
          brand_materials: mat,
          brand_id: form.brand_id.trim() || undefined,
          model_name: BRAND_AI_DRAFT_MODEL,
        },
      });
      setForm(draftPayloadToForm(data.draft));
      setAiOnboardNoticeVisible(true);
      if (aiDetailsRef.current) {
        aiDetailsRef.current.open = false;
      }
      showToast(`Onboard draft ready (${data.model_used}).`);
    } catch (e) {
      showToast(e.message || String(e), "error");
    } finally {
      setAiBusy(false);
    }
  }

  const steps = ["Identity", "Look & feel", "Voice & channels", "Governance & prompts"];
  const last = step === steps.length - 1;

  async function save() {
    setBusy(true);
    try {
      const formForPayload =
        mode === "create"
          ? {
              ...form,
              brand_id: (form.brand_id || "").trim() || crypto.randomUUID().toLowerCase(),
            }
          : form;
      const payload = buildBrandCreatePayload(formForPayload);
      if (mode === "create") {
        await client.request("/api/brands", { method: "POST", json: payload });
        const id = payload.brand_id;
        if (logoFile && apiKey) {
          await uploadLogoFile({ apiBase, apiKey, brandId: id, file: logoFile });
        }
        showToast(`Brand “${payload.display_name || id}” created.`);
      } else if (mode === "edit" && brandId) {
        const body = buildBrandPutConfiguration(form);
        if (body.brand_id !== brandId) {
          showToast("Brand ID in form must match the brand being edited.", "error");
          setBusy(false);
          return;
        }
        await client.request(`/api/brands/${encodeURIComponent(brandId)}`, {
          method: "PUT",
          json: body,
        });
        if (logoFile && apiKey) {
          await uploadLogoFile({ apiBase, apiKey, brandId, file: logoFile });
        }
        showToast("Brand updated.");
      }
      await loadBrands();
      onSaved?.();
      onClose();
    } catch (e) {
      showToast(e.message || String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  const footer = (
    <div className="row-between modal-footer-row">
      <div className="btn-row">
        {step > 0 && (
          <button type="button" className="btn btn-secondary" onClick={() => setStep((s) => s - 1)} disabled={busy || aiBusy}>
            Back
          </button>
        )}
      </div>
      <div className="btn-row">
        <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy || aiBusy}>
          Cancel
        </button>
        {!last && (
          <button type="button" className="btn btn-primary" onClick={() => setStep((s) => s + 1)} disabled={busy || aiBusy}>
            Next
          </button>
        )}
        {last && (
          <button type="button" className="btn btn-primary" onClick={save} disabled={busy || loading || aiBusy}>
            {busy ? "Saving…" : mode === "create" ? "Create brand" : "Save changes"}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <Modal
      open={open}
      title={
        mode === "create"
          ? "Create brand"
          : `Edit brand${form.display_name ? ` — ${form.display_name}` : ""}`
      }
      onClose={onClose}
      footer={footer}
    >
      <div className="wizard-logo-top">
        <label className="os-dropzone brand-modal-logo-drop">
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="os-dropzone-input"
            onChange={(e) => setLogoFile(e.target.files?.[0] || null)}
            disabled={loading}
          />
          <span className="os-dropzone-text">
            {logoFile
              ? `Selected: ${logoFile.name}`
              : "Upload brand logo (PNG, JPEG, WebP) — optional"}
          </span>
        </label>
        <small className="field-hint brand-modal-logo-hint">Uploaded when you save this brand.</small>
      </div>

      {mode === "create" && (
        <details ref={aiDetailsRef} className="wizard-ai-details">
          <summary className="wizard-ai-summary">
            <span className="wizard-ai-summary__icon" aria-hidden>
              <AiAssistantGlyph gradId={aiSummaryGlyphGradId} size={22} className="ai-onboard-glyph ai-onboard-glyph--inline" />
            </span>
            <span className="wizard-ai-summary__label">Onboard with AI (optional)</span>
          </summary>
          <p className="help wizard-ai-help">
            Optional shortcut: paste what you know about the brand and we&apos;ll suggest answers in the steps below.
            You can still fill everything by hand.
          </p>
          <div className="os-ai-bar brand-modal-os-ai-bar">
            <textarea
              className="os-ai-bar-input brand-modal-os-ai-notes"
              rows={3}
              value={aiMaterials}
              onChange={(e) => setAiMaterials(e.target.value)}
              placeholder="Paste guidelines, tone, colors, fonts, examples… (min 30 characters)"
              disabled={aiBusy}
            />
            <button
              type="button"
              className="os-ai-bar-send"
              onClick={runAiDraft}
              disabled={aiBusy || loading || (aiMaterials || "").trim().length < 30}
              title="Suggest draft"
              aria-label={aiBusy ? "Working" : "Suggest draft"}
            >
              {aiBusy ? "…" : "➤"}
            </button>
          </div>
        </details>
      )}

      {mode === "create" && aiOnboardNoticeVisible && (
        <div className="ai-onboard-notice" role="status">
          <div className="ai-onboard-notice__glyph">
            <AiAssistantGlyph gradId={aiGlyphGradId} />
          </div>
          <div className="ai-onboard-notice__body">
            <p className="ai-onboard-notice__title">Check carefully, then save</p>
            <ul className="ai-onboard-notice__list">
              <li>Review each step yourself — AI suggestions can be wrong or incomplete.</li>
              <li>When everything looks right, go to the last step and save your brand.</li>
              <li>
                Don&apos;t forget to <strong>upload your logo</strong> at the top of this window if you want it on your
                creatives{logoFile ? " (you already picked a file — it will upload when you save)." : "."}
              </li>
            </ul>
            <button type="button" className="btn btn-ghost btn-sm ai-onboard-notice__dismiss" onClick={() => setAiOnboardNoticeVisible(false)}>
              Dismiss
            </button>
          </div>
        </div>
      )}

      <div className="wizard-steps" aria-hidden>
        {steps.map((label, i) => (
          <button
            key={label}
            type="button"
            className={`wizard-step ${i === step ? "active" : ""} ${i < step ? "done" : ""}`}
            onClick={() => setStep(i)}
          >
            <span className="wizard-idx">{i + 1}</span>
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="help">Loading brand…</p>
      ) : (
        <>
          {step === 0 && (
            <div className="wizard-panel">
              <label className="field">
                Display name <span className="req">*</span>
                <input value={form.display_name} onChange={(e) => setF("display_name", e.target.value)} />
                {mode === "create" && (
                  <small className="field-hint">A unique internal ID is assigned automatically when you save.</small>
                )}
              </label>
              <label className="field">
                Tagline
                <input value={form.tagline} onChange={(e) => setF("tagline", e.target.value)} />
              </label>
              <label className="field">
                Legal suffix
                <input value={form.legal_suffix} onChange={(e) => setF("legal_suffix", e.target.value)} />
              </label>
            </div>
          )}

          {step === 1 && (
            <div className="wizard-panel">
              <label className="field">
                Primary colors (comma-separated hex)
                <input value={form.colors_primary} onChange={(e) => setF("colors_primary", e.target.value)} />
              </label>
              <label className="field">
                Secondary colors
                <input value={form.colors_secondary} onChange={(e) => setF("colors_secondary", e.target.value)} />
              </label>
              <label className="field">
                Color usage rules
                <textarea rows={3} value={form.colors_usage_rules} onChange={(e) => setF("colors_usage_rules", e.target.value)} />
              </label>
              <label className="field">
                Primary font
                <input value={form.typography_primary_font} onChange={(e) => setF("typography_primary_font", e.target.value)} />
              </label>
              <label className="field">
                Headline font
                <input value={form.typography_headline_font} onChange={(e) => setF("typography_headline_font", e.target.value)} />
              </label>
              <label className="field">
                Body font
                <input value={form.typography_body_font} onChange={(e) => setF("typography_body_font", e.target.value)} />
              </label>
              <label className="field">
                Typography notes
                <textarea rows={2} value={form.typography_notes} onChange={(e) => setF("typography_notes", e.target.value)} />
              </label>
            </div>
          )}

          {step === 2 && (
            <div className="wizard-panel">
              <label className="field">
                Tone keywords (comma-separated)
                <input value={form.voice_tone_keywords} onChange={(e) => setF("voice_tone_keywords", e.target.value)} />
              </label>
              <label className="field">
                Writing style
                <textarea rows={2} value={form.voice_writing_style} onChange={(e) => setF("voice_writing_style", e.target.value)} />
              </label>
              <label className="field">
                Target audience
                <textarea rows={2} value={form.voice_target_audience} onChange={(e) => setF("voice_target_audience", e.target.value)} />
              </label>
              <label className="field">
                Preferred platforms (comma-separated)
                <input value={form.social_platforms} onChange={(e) => setF("social_platforms", e.target.value)} />
              </label>
              <label className="field">
                Per-platform hints (optional, one line per platform: <code>instagram: …</code>)
                <textarea
                  rows={4}
                  className="code-input"
                  value={form.platform_hints_lines}
                  onChange={(e) => setF("platform_hints_lines", e.target.value)}
                  placeholder={"instagram: Bold hero, strong CTA\nlinkedin: Editorial, career-focused"}
                />
              </label>
              <div className="field-row">
                <label className="field">
                  Default aspect ratio
                  <input value={form.default_aspect_ratio} onChange={(e) => setF("default_aspect_ratio", e.target.value)} />
                </label>
                <label className="field">
                  Default image size
                  <input value={form.default_image_size} onChange={(e) => setF("default_image_size", e.target.value)} />
                </label>
              </div>
              <label className="field">
                Content categories (comma-separated)
                <input value={form.content_categories} onChange={(e) => setF("content_categories", e.target.value)} />
              </label>
              <label className="field">
                Recurring themes / messaging lines (one per line or comma-separated)
                <textarea rows={3} value={form.content_themes} onChange={(e) => setF("content_themes", e.target.value)} />
              </label>
              <label className="field">
                Hashtag style prefs
                <textarea rows={2} value={form.hashtag_style} onChange={(e) => setF("hashtag_style", e.target.value)} />
              </label>
              <label className="field">
                Caption style prefs
                <textarea rows={2} value={form.caption_style} onChange={(e) => setF("caption_style", e.target.value)} />
              </label>
              <label className="field">
                Banned phrases (comma-separated)
                <input value={form.banned_phrases} onChange={(e) => setF("banned_phrases", e.target.value)} />
              </label>
            </div>
          )}

          {step === 3 && (
            <div className="wizard-panel">
              <p className="help">
                Paste your full <strong>brand constitution</strong> (colors, typography, mood, CTAs, avoid list) into{" "}
                <strong>Governance prompt</strong> if it fits one document—e.g. &quot;You are the official N+ Social Media
                …&quot;. Use the extra boxes below for layout, CTA, visual, and &quot;avoid&quot; sections so the model
                always receives them even when the main paste is shorter.
              </p>
              <label className="field">
                Governance prompt <span className="req">*</span> (full brand bible — min 20 chars)
                <textarea
                  rows={14}
                  className="code-input"
                  value={form.governance_prompt_template}
                  onChange={(e) => setF("governance_prompt_template", e.target.value)}
                  placeholder="You are the official … Brand agent. Paste full guidelines here."
                />
              </label>
              <label className="field">
                Supplementary design guidelines
                <textarea rows={3} value={form.design_guidelines} onChange={(e) => setF("design_guidelines", e.target.value)} />
              </label>
              <label className="field">
                Layout, spacing & composition (canvas sizes, margins, logo placement)
                <textarea rows={4} value={form.layout_spacing_rules} onChange={(e) => setF("layout_spacing_rules", e.target.value)} />
              </label>
              <label className="field">
                Button & CTA rules (shapes, colors, example CTAs)
                <textarea rows={4} value={form.cta_button_rules} onChange={(e) => setF("cta_button_rules", e.target.value)} />
              </label>
              <label className="field">
                Visual & design style (imagery, backgrounds, gradients, mood)
                <textarea rows={4} value={form.visual_style_rules} onChange={(e) => setF("visual_style_rules", e.target.value)} />
              </label>
              <label className="field">
                Avoid (explicit do-not list)
                <textarea rows={3} value={form.avoid_rules} onChange={(e) => setF("avoid_rules", e.target.value)} />
              </label>
              <label className="field">
                Slide intro template (optional — prefix before post copy in the user message)
                <textarea rows={3} value={form.slide_intro_template} onChange={(e) => setF("slide_intro_template", e.target.value)} />
              </label>
              <label className="field">
                Slide user prompt suffix (appended after post copy)
                <textarea rows={5} className="code-input" value={form.slide_user_prompt_suffix} onChange={(e) => setF("slide_user_prompt_suffix", e.target.value)} />
              </label>
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
