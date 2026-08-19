# Experiment: multi-image generation (one API call)

Isolated spike before changing `backend/generation/`. Compares **one request, multiple images** vs what production does today (sequential calls).

## Setup

```powershell
cd experiments\multi_image_generation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Keys in **`backend/.env`**:

- `OPENAI_API_KEY` — OpenAI batch tests
- `GOOGLE_API_KEY` — Gemini tests

Uses `backend/assets/default_logo.jpg` for logo-reference flows.

## Run

**OpenAI** — single request with `n` (production-like = `edit_reference`):

```powershell
python run_experiment.py openai --count 3 --mode edit_reference --model gpt-image-1-mini
python run_experiment.py openai --count 3 --compare-sequential
```

**OpenAI** — plain text generate (no logo):

```powershell
python run_experiment.py openai --count 3 --mode generate --model gpt-image-1-mini
```

**Gemini** — one `generateContent` call per strategy:

```powershell
python run_experiment.py gemini --count 3 --model gemini-2.5-flash-image
python run_experiment.py gemini --count 3 --model gemini-3-pro-image-preview --include-candidate-count
```

**Both providers** (quick smoke, count=2):

```powershell
python run_experiment.py all --count 2
```

## Output

Each run creates:

```
output/<timestamp>_<provider>_<label>/
  manifest.json    # counts, timing, errors, no base64
  image_01.png
  image_02.png
  ...
```

Summaries: `output/last_openai_summary.json`, `output/last_gemini_summary.json`.

## What each strategy tests

| Provider | Label | Hypothesis |
|----------|--------|------------|
| OpenAI | `edit_reference` + `n` | Same as Rankify generate path; should return `data[]` length = n |
| OpenAI | `generate` + `n` | Text-only baseline without logo |
| OpenAI | `sequential` | N × `n=1` (current production pattern) |
| Gemini | `image_only` | `responseModalities: [IMAGE]` + prompt asking for N slides |
| Gemini | `text_and_image` | `[TEXT, IMAGE]` + same prompt (Stack Overflow pattern) |
| Gemini | `candidate_count` | `candidateCount: N` — expect API error or 1 image |

Gemini extractor saves **every** `inlineData` image part in the response (not only the first).

## How to read results

Record in `manifest.json`:

- `requested_count` vs `images_saved` — did we get N files?
- `elapsed_seconds` — batch vs sequential cost in time
- `image_parts_in_response` (Gemini) — how many image parts the API returned
- `error` — API rejection (e.g. invalid `candidateCount`, size)

**Success for production integration:**

- OpenAI: `images_saved == requested_count` on `edit_reference` with your chosen model.
- Gemini: only if `images_saved >= requested_count` reliably on `image_only` or `text_and_image`; otherwise keep sequential in the app.

## Next step (main codebase)

After you pick a winning approach, we wire it into:

- `generation/image_providers/openai_provider.py` — pass `n=slide_count`, save all `data[]`
- `generation/slide_pipeline.py` — optional single-call path per provider
- `frontend` — `num_images` control in Creative Studio

Do **not** import this experiment folder from production code.
