"""Strict prompts for AI image refinement (edit-in-place, not full redesign)."""

from __future__ import annotations

from brands.schemas import BrandConfiguration


EDIT_GOVERNANCE_SYSTEM = """You are a precision image editor for branded social marketing assets.

The next part of this message contains the SOURCE IMAGE as inline image data. Treat every pixel outside the user's explicit change request as ground truth to preserve.

NON-NEGOTIABLE RULES:
1) Apply ONLY what the USER EDIT REQUEST asks for. Make the smallest change that fulfills the request.
2) Do NOT fully regenerate or redesign the piece. Do NOT replace the layout, composition, or canvas crop unless the user explicitly asks to change layout or composition.
3) Preserve unless the user explicitly asks to change them: existing on-image typography and copy, logo placement and logo artwork, subject placement, and overall brand look.
4) Do NOT add watermarks, device frames, browser chrome, or spurious UI. Do NOT add new headline text unless the user asked for copy changes.
5) Output exactly ONE full-frame raster image matching the requested aspect configuration; no letterboxing unless the user asked for it.
6) If the request conflicts with brand safety, prefer minimal safe edits and avoid removing required brand marks.
"""


def build_brand_edit_context_snippet(cfg: BrandConfiguration) -> str:
    """Short brand anchor so the model remembers palette / name without full governance."""
    prim = ", ".join(cfg.colors.primary[:4]) if cfg.colors.primary else ""
    lines = [
        f"Brand display name: {cfg.display_name}",
        f"Primary palette (preserve unless edit says otherwise): {prim}" if prim else "",
        (cfg.colors.usage_rules or "").strip()[:400] if (cfg.colors.usage_rules or "").strip() else "",
    ]
    return "\n".join(x for x in lines if x).strip()


def build_edit_user_prompt(instruction: str, brand_snippet: str) -> str:
    inst = (instruction or "").strip()
    block = f"""USER EDIT REQUEST — apply minimally and locally:
{inst}

If anything above is ambiguous, choose the smallest visible edit that satisfies it. Do not change unrelated areas."""
    if brand_snippet:
        return f"BRAND CONTEXT (reference only; do not print as text on the image):\n{brand_snippet}\n\n{block}"
    return block
