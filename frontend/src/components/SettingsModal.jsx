import { useState } from "react";
import { Modal } from "./Modal.jsx";
import { useApp } from "../context/AppContext.jsx";

export function SettingsModal({ open, onClose }) {
  const {
    apiBase,
    setApiBase,
    apiKey,
    setApiKey,
    saveConnection,
    client,
    loadBrands,
    showToast,
  } = useApp();
  const [busy, setBusy] = useState(false);

  async function bootstrap() {
    setBusy(true);
    try {
      await client.request("/api/brands/bootstrap-demo", { method: "POST" });
      await loadBrands();
      showToast("Demo brand ready (demo-ai-certs).");
    } catch (e) {
      showToast(e.message || String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      title="Workspace settings"
      onClose={onClose}
      footer={
        <div className="row-between">
          <button type="button" className="btn btn-secondary" onClick={bootstrap} disabled={busy}>
            Bootstrap demo brand
          </button>
          <div className="btn-row">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Close
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                saveConnection();
                onClose();
              }}
            >
              Save
            </button>
          </div>
        </div>
      }
    >
      <p className="help">
        <code>x-api-key</code> must match <code>API_KEY</code> in <code>backend/.env</code>. In local dev, leave{" "}
        <strong>API base URL</strong> empty so requests use the Vite proxy to your API (default{" "}
        <code>http://127.0.0.1:9600</code>). Set a full URL only if the API is not behind the dev proxy.
      </p>
      <label className="field">
        API base URL
        <input
          value={apiBase}
          onChange={(e) => setApiBase(e.target.value)}
          placeholder="(empty in dev = proxy to backend)"
        />
      </label>
      <label className="field">
        x-api-key
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="Your secret API key"
        />
      </label>
    </Modal>
  );
}
