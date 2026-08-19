# Experiment: AI-assisted brand JSON (OpenAI)

Goal: paste unstructured brand material and obtain a **`BrandCreatePayload`**-compatible object (same shape as `POST /api/brands`), using **`brand_id` = a new UUID** (lowercase, valid slug for this codebase).

This folder is **isolated** from FastAPI and the main `requirements.txt`. Install deps here only.

### OpenAI structured outputs vs `BrandCreatePayload`

The production schema uses `platform_hints.hints` as a **string map**, which OpenAI strict structured outputs reject. The server uses **`OpenAIBrandCreateDraft`** in `backend/brands/openai_brand_draft.py` (`platform_hints.entries` as a list of `{ platform_id, hint }`) and converts to **`BrandCreatePayload`** after the API returns.

The CLI script `run_draft.py` calls **`brands.ai_brand_draft_service.draft_brand_create_payload_from_materials`** (same code path as `POST /api/brands/ai-draft`).

## Setup

1. Add your key to **`backend/.env`** (or repo-root `.env`):

   ```env
   OPENAI_API_KEY=sk-...
   ```

2. Create a virtualenv (recommended) and install experiment deps:

   ```powershell
   cd experiments\brand_ai_onboarding
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   The script also needs packages from the main backend (pydantic, dotenv). Either:

   - install from repo root: `pip install -r ..\..\requirements.txt`, or  
   - use the same venv you already use for `backend` if it has pydantic + python-dotenv.

3. Run:

   ```powershell
   # From this directory, with cwd = experiments/brand_ai_onboarding
   python run_draft.py --input sample_brand_materials.example.txt
   ```

   Or pipe stdin:

   ```powershell
   Get-Content my_notes.txt | python run_draft.py
   ```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `gpt-4o-2024-08-06` | Snapshots that support structured outputs (e.g. `gpt-4o-mini`, `gpt-4o-2024-08-06`). |
| `--brand-id` | *(auto UUID)* | Force a specific id (must still pass `validate_brand_id`). |
| `-o out.json` | stdout | Write validated JSON to a file. |

## Output

- Prints **validated** JSON (pretty-printed) that should load as `BrandCreatePayload` / `BrandConfiguration` in the app after you copy assets and call `POST /api/brands`.
- If the model **refuses**, the script prints the refusal and exits non-zero.
- If **structured parse** fails (API or model), the script falls back to **JSON object** mode, validates as **`OpenAIBrandCreateDraft`**, then converts to **`BrandCreatePayload`** (so `content_themes` must be an object with `categories` / `recurring_themes`, not a bare array).

## Next step after you are happy with drafts

Wire a real `POST /api/brands/draft` route, a UI (paste → review JSON → save), and optionally add `openai` to the main `requirements.txt`.
