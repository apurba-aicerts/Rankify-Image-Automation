import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApp } from "../context/AppContext.jsx";

export function BrandGalleryPage() {
  const { brandId: rawId } = useParams();
  const brandId = rawId ? decodeURIComponent(rawId) : "";
  const { client, showToast } = useApp();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!brandId) return;
    let cancelled = false;
    setLoading(true);
    client
      .request(`/api/brands/${encodeURIComponent(brandId)}/gallery`)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) showToast(e.message || String(e), "error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [brandId, client, showToast]);

  const images = data?.images || [];

  return (
    <div className="page gallery-page">
      <header className="page-head">
        <div>
          <Link to="/" className="back-link">
            ← Brands
          </Link>
          <h1>Generated assets</h1>
          <p className="lede">
            Gallery for <code>{brandId}</code> — signed view URLs expire after the server TTL.
          </p>
          <p className="gallery-studio-link">
            <Link to={`/brands/${encodeURIComponent(brandId)}/studio`}>Open AI Creative Studio for this brand →</Link>
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => {
            setLoading(true);
            client
              .request(`/api/brands/${encodeURIComponent(brandId)}/gallery`)
              .then(setData)
              .catch((e) => showToast(e.message || String(e), "error"))
              .finally(() => setLoading(false));
          }}
          disabled={loading || !brandId}
        >
          {loading ? "Loading…" : "Reload"}
        </button>
      </header>

      {images.length === 0 && !loading && (
        <div className="empty-state">
          <p>No images in this gallery yet. Generate from the brand card on the dashboard.</p>
        </div>
      )}

      <div className="gallery-grid">
        {images.map((img) => (
          <figure key={img.filename} className="gallery-item">
            <a href={img.url} target="_blank" rel="noreferrer">
              <img src={img.url} alt={img.filename} loading="lazy" />
            </a>
            <figcaption>
              <code>{img.filename}</code>
              <span className="meta">
                {(img.size_bytes / 1024).toFixed(1)} KB · {img.age_hours}h old
              </span>
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}
