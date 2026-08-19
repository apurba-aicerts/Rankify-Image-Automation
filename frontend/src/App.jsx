import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout.jsx";
import { Dashboard } from "./pages/Dashboard.jsx";
import { BrandGalleryPage } from "./pages/BrandGalleryPage.jsx";
import { CreativeStudioPage } from "./pages/CreativeStudioPage.jsx";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="brands/:brandId/studio" element={<CreativeStudioPage />} />
        <Route path="brands/:brandId/gallery" element={<BrandGalleryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
