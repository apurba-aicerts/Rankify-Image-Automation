/** UI checklist: brand system coverage (best-effort from JSON; logo file checked async in studio). */

export function enforcementFromBrand(brand) {
  if (!brand) {
    return {
      governance: false,
      palette: false,
      typography: false,
      logo: false,
    };
  }
  const gov = (brand.generation?.governance_prompt_template || "").trim().length >= 40;
  const palette = (brand.colors?.primary || []).length > 0;
  const typo = Boolean(
    (brand.typography?.headline_font || "").trim() ||
      (brand.typography?.body_font || "").trim() ||
      (brand.typography?.primary_font || "").trim()
  );
  return {
    governance: gov,
    palette,
    typography: typo,
    logo: null,
  };
}
