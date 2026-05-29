import { useEffect, useState } from "react";
import { Modal } from "./Modal.jsx";
import { useApp } from "../context/AppContext.jsx";
import { SAMPLE_POST } from "../constants/defaults.js";

export function GenerateImageModal({ open, brandId, onClose, onGenerated }) {
  const { client, showToast } = useApp();
  const [content, setContent] = useState(SAMPLE_POST);
  const [modelName, setModelName] = useState("gemini-3-pro-image-preview");
  const [numImages, setNumImages] = useState(1);
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [imageSize, setImageSize] = useState("2K");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [models, setModels] = useState([]);
  const [ratios, setRatios] = useState([]);
  const [sizes, setSizes] = useState([]);

  useEffect(() => {
    if (!open || !brandId) return;
    setResult(null);
    let cancelled = false;
    (async () => {
      try {
        const [brand, meta, mlist] = await Promise.all([
          client.request(`/api/brands/${encodeURIComponent(brandId)}`),
          client.request("/api/image-sizes"),
          client.request("/api/models"),
        ]);
        if (cancelled) return;
        setAspectRatio(brand.social_defaults?.default_aspect_ratio || "1:1");
        setImageSize(brand.social_defaults?.default_image_size || "2K");
        setRatios(meta.aspect_ratios || []);
        setSizes(meta.image_sizes || []);
        const ids = (mlist.models || []).map((m) => m.model_name).filter(Boolean);
        setModels(ids);
        if (ids.length && !ids.includes(modelName)) setModelName(ids[0]);
      } catch (e) {
        if (!cancelled) showToast(e.message || String(e), "error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, brandId, client, showToast]);

  async function runGenerate() {
    if (!brandId) return;
    setBusy(true);
    setResult(null);
    try {
      const body = {
        brand_id: brandId,
        content: content.trim(),
        model_name: modelName,
        num_images: numImages,
        aspect_ratio: aspectRatio,
        image_size: modelName === "gemini-3-pro-image-preview" ? imageSize : undefined,
      };
      const data = await client.request("/api/generate", { method: "POST", json: body });
      setResult(data);
      showToast(data.message || "Generation complete.");
      onGenerated?.();
    } catch (e) {
      showToast(e.message || String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      title={`Generate images — ${brandId || ""}`}
      onClose={onClose}
      footer={
        <div className="btn-row">
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>
            Close
          </button>
          <button type="button" className="btn btn-primary" onClick={runGenerate} disabled={busy || !brandId}>
            {busy ? "Generating…" : "Run pipeline"}
          </button>
        </div>
      }
    >
      <p className="help">
        Content uses your brand&apos;s governance prompt, colors, and generation rules automatically. Paste structured
        post copy (TITLE / SUBTITLE / BODY / CTA).
      </p>
      <label className="field">
        Model
        <select value={modelName} onChange={(e) => setModelName(e.target.value)}>
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>
      <div className="field-row">
        <label className="field">
          Slides
          <input
            type="number"
            min={1}
            max={10}
            value={numImages}
            onChange={(e) => setNumImages(Number(e.target.value))}
          />
        </label>
        <label className="field">
          Aspect ratio
          <select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)}>
            {(ratios.length ? ratios : ["1:1", "4:5", "16:9"]).map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        {modelName === "gemini-3-pro-image-preview" && (
          <label className="field">
            Image size
            <select value={imageSize} onChange={(e) => setImageSize(e.target.value)}>
              {(sizes.length ? sizes : ["1K", "2K", "4K"]).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <label className="field">
        Structured post copy
        <textarea rows={12} value={content} onChange={(e) => setContent(e.target.value)} className="code-input" />
      </label>

      {result?.images?.length > 0 && (
        <div className="gen-results">
          <h4>Output</h4>
          <div className="gen-thumbs">
            {result.images.map((img) => (
              <a key={img.filename} href={img.url} target="_blank" rel="noreferrer" className="gen-thumb">
                <img src={img.url} alt={img.filename} />
                <span>{img.filename}</span>
              </a>
            ))}
          </div>
          <p className="help subtle">
            Total ${result.total_price_usd?.toFixed?.(4) ?? result.total_price_usd} · {result.model_used}
          </p>
        </div>
      )}
    </Modal>
  );
}
