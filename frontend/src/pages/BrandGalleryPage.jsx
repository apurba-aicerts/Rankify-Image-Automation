import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApp } from "../context/AppContext.jsx";

export function BrandGalleryPage() {
  const { brandId: rawId } = useParams();
  const brandId = rawId ? decodeURIComponent(rawId) : "";
  const { client, showToast } = useApp();
  const [data, setData] = useState(null);
  const [brand, setBrand] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadGallery = useCallback(() => {
    if (!brandId) return Promise.resolve();
    return Promise.all([
      client.request(`/api/brands/${encodeURIComponent(brandId)}/gallery`),
      client.request(`/api/brands/${encodeURIComponent(brandId)}`).catch(() => null),
    ]).then(([gallery, brandConfig]) => {
      setData(gallery);
      setBrand(brandConfig);
    });
  }, [brandId, client]);

  useEffect(() => {
    if (!brandId) return;
    let cancelled = false;
    setLoading(true);
    loadGallery()
      .catch((e) => {
        if (!cancelled) showToast(e.message || String(e), "error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [brandId, loadGallery, showToast]);

  const images = data?.images || [];
  const displayName = brand?.display_name || brandId;
  const total = data?.total ?? images.length;

  return (
    <div className="page gallery-page">
      <header className="page-head">
        <div>
          <Link to="/" className="back-link">
            ← Brands
          </Link>
          <h1>{displayName}</h1>
          <p className="lede">
            Generation history — {total === 1 ? "1 image" : `${total} images`} stored for up to 30 days.
            Download links refresh when you reload this page.
          </p>
          <p className="gallery-studio-link">
            <Link to={`/brands/${encodeURIComponent(brandId)}/studio`}>← Back to Creative Studio</Link>
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => {
            setLoading(true);
            loadGallery()
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
          <p>No generated images yet. Open Creative Studio to create your first visual.</p>
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
