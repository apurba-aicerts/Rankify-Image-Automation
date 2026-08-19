import { useApp } from "../context/AppContext.jsx";
import { useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { SettingsModal } from "./SettingsModal.jsx";

export function Layout() {
  const { toast } = useApp();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const loc = useLocation();

  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="brand-mark">
          <span className="brand-dot" />
          Rankify Creative OS
        </Link>
        <nav className="topnav">
          <Link to="/" className={loc.pathname === "/" ? "active" : ""}>
            Brands
          </Link>
        </nav>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setSettingsOpen(true)}
        >
          Settings
        </button>
      </header>

      <main className="main">
        <Outlet />
      </main>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />

      {toast && <div className={`toast toast-${toast.variant}`}>{toast.message}</div>}
    </div>
  );
}
