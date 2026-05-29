import { useCallback, useEffect, useState } from "react";
import { BrandCard, CreateBrandCard } from "../components/BrandCard.jsx";
import { BrandFormModal } from "../components/BrandFormModal.jsx";
import { useApp } from "../context/AppContext.jsx";

export function Dashboard() {
  const { client, brands, loadBrands, showToast } = useApp();
  const [details, setDetails] = useState({});
  const [statsByBrand, setStatsByBrand] = useState({});
  /** false while fetching details+gallery for the current `brands` list */
  const [insightsReady, setInsightsReady] = useState(true);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [editId, setEditId] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      await loadBrands();
    } catch (e) {
      showToast(e.message || String(e), "error");
    } finally {
      setLoading(false);
    }
  }, [loadBrands, showToast]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!brands.length) {
      setDetails({});
      setStatsByBrand({});
      setInsightsReady(true);
      return;
    }
    let cancelled = false;
    setInsightsReady(false);
    (async () => {
      const rows = await Promise.all(
        brands.map(async (s) => {
          try {
            const [d, g] = await Promise.all([
              client.request(`/api/brands/${encodeURIComponent(s.brand_id)}`),
              client.request(`/api/brands/${encodeURIComponent(s.brand_id)}/gallery`),
            ]);
            const total = g?.total ?? 0;
            const imgs = g?.images || [];
            const thisWeek = imgs.filter((img) => (img.age_hours ?? 999) <= 168).length;
            return { brandId: s.brand_id, detail: d, stats: { total, thisWeek } };
          } catch {
            return { brandId: s.brand_id, detail: null, stats: { total: 0, thisWeek: 0 } };
          }
        })
      );
      if (cancelled) return;
      setDetails(Object.fromEntries(rows.map((r) => [r.brandId, r.detail])));
      setStatsByBrand(Object.fromEntries(rows.map((r) => [r.brandId, r.stats])));
      setInsightsReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [brands, client]);

  async function deleteBrand(brandId, displayName) {
    const label = displayName || brandId;
    const ok = window.confirm(
      `Delete workspace “${label}”?\n\nThis removes the brand profile, logo, and all generated images. This cannot be undone.`,
    );
    if (!ok) return;
    try {
      await client.request(`/api/brands/${encodeURIComponent(brandId)}`, { method: "DELETE" });
      if (editId === brandId) setEditId(null);
      await loadBrands();
      showToast(`Workspace “${label}” deleted.`);
    } catch (e) {
      showToast(e.message || String(e), "error");
    }
  }

  return (
    <div className="page dashboard">
      <header className="page-head">
        <div>
          <h1>Brand studios</h1>
          <p className="lede">
            Production-grade workspaces for every identity—generate on-brand visuals, review assets, and tune
            governance from one dashboard.
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {brands.length === 0 && !loading && (
        <div className="empty-state">
          <p>No workspaces yet. Create one or use Settings → Bootstrap demo brand.</p>
        </div>
      )}

      <section className="brand-grid" aria-label="Brand workspaces">
        {brands.map((s) => (
          <BrandCard
            key={s.brand_id}
            summary={s}
            detail={details[s.brand_id]}
            stats={statsByBrand[s.brand_id]}
            statsLoading={!insightsReady}
            onEdit={setEditId}
            onDelete={deleteBrand}
          />
        ))}
        <CreateBrandCard onClick={() => setCreateOpen(true)} />
      </section>

      <BrandFormModal open={createOpen} mode="create" onClose={() => setCreateOpen(false)} />
      <BrandFormModal open={Boolean(editId)} mode="edit" brandId={editId} onClose={() => setEditId(null)} />
    </div>
  );
}
