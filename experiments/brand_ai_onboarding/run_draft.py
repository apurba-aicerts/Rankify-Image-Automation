"""
CLI wrapper for the production OpenAI brand draft service (``brands.ai_brand_draft_service``).

Usage::
  cd experiments/brand_ai_onboarding
  pip install -r requirements.txt
  pip install -r ../../requirements.txt
  # OPENAI_API_KEY in backend/.env

  python run_draft.py --input sample_brand_materials.example.txt -o draft.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_BACKEND = _REPO / "backend"
if not _BACKEND.is_dir():
    print("Expected backend/ at", _BACKEND, file=sys.stderr)
    sys.exit(1)
sys.path.insert(0, str(_BACKEND))

try:
    from dotenv import load_dotenv  # noqa: E402
except ImportError:

    def load_dotenv(*_a, **_k):  # type: ignore[no-redef]
        return False


load_dotenv(_BACKEND / ".env")
load_dotenv(_REPO / ".env")

from brands.ai_brand_draft_service import draft_brand_create_payload_from_materials  # noqa: E402


def _read_input_text(args: argparse.Namespace) -> str:
    if args.input:
        p = Path(args.input)
        if not p.is_file():
            print("Input file not found:", p, file=sys.stderr)
            sys.exit(1)
        return p.read_text(encoding="utf-8")
    data = sys.stdin.read()
    if not data.strip():
        print("No input: provide --input file or pipe text on stdin.", file=sys.stderr)
        sys.exit(1)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAI -> BrandCreatePayload (calls backend service)")
    parser.add_argument("--input", "-i", type=Path, help="UTF-8 file with pasted brand material")
    parser.add_argument("--brand-id", type=str, default=None, help="Optional slug; default UUID from service")
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-2024-08-06",
        help="OpenAI chat model",
    )
    parser.add_argument("-o", "--output", type=Path, default=None, help="Write JSON to file")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Missing OPENAI_API_KEY (add to backend/.env).", file=sys.stderr)
        sys.exit(1)

    blob = _read_input_text(args)
    bid = args.brand_id.strip().lower() if args.brand_id and args.brand_id.strip() else None

    payload = draft_brand_create_payload_from_materials(
        brand_materials=blob,
        brand_id=bid,
        model_name=args.model,
        openai_api_key=os.environ["OPENAI_API_KEY"],
    )

    text = json.dumps(payload.model_dump(mode="json"), indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        print("Wrote", args.output.resolve())
    else:
        print(text)


if __name__ == "__main__":
    main()
