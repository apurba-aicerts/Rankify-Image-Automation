import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { createApiClient, loadStoredSettings, persistSettings } from "../lib/api.js";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [apiBase, setApiBase] = useState(() => loadStoredSettings().apiBase);
  const [apiKey, setApiKey] = useState(() => loadStoredSettings().apiKey);
  const [brands, setBrands] = useState([]);
  const [toast, setToast] = useState(null);

  const client = useMemo(
    () => createApiClient({ apiBase, apiKey }),
    [apiBase, apiKey]
  );

  const showToast = useCallback((message, variant = "info") => {
    setToast({ message, variant });
    window.setTimeout(() => setToast(null), 4200);
  }, []);

  const loadBrands = useCallback(async () => {
    const data = await client.request("/api/brands");
    setBrands(data.brands || []);
    return data.brands || [];
  }, [client]);

  const saveConnection = useCallback(() => {
    persistSettings(apiBase, apiKey);
    showToast("Connection saved in this browser.");
  }, [apiBase, apiKey, showToast]);

  const value = useMemo(
    () => ({
      apiBase,
      setApiBase,
      apiKey,
      setApiKey,
      client,
      brands,
      setBrands,
      loadBrands,
      saveConnection,
      showToast,
      toast,
    }),
    [
      apiBase,
      apiKey,
      client,
      brands,
      loadBrands,
      saveConnection,
      showToast,
      toast,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
