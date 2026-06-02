#!/usr/bin/env python3
"""
Compare multi-image generation: one API call vs sequential.

Usage (from this directory)::

  pip install -r requirements.txt
  # GOOGLE_API_KEY and OPENAI_API_KEY in ../../backend/.env

  python run_experiment.py openai --count 3
  python run_experiment.py gemini --count 3 --model gemini-2.5-flash-image
  python run_experiment.py all --count 2

Outputs land in ``output/<timestamp>_.../`` with manifest.json and image_*.png.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib_io import bootstrap_paths, default_logo_path, load_prompt, require_key

_HERE = Path(__file__).resolve().parent


def _print_record(rec: dict) -> None:
    ok = not rec.get("error") and (rec.get("images_saved") or 0) > 0
    status = "OK" if ok else "FAIL"
    print(
        f"  [{status}] {rec.get('provider')} | {rec.get('model')} | "
        f"strategy/mode={rec.get('strategy') or rec.get('mode')} | "
        f"requested={rec.get('requested_count')} saved={rec.get('images_saved')} "
        f"elapsed={rec.get('elapsed_seconds')}s"
    )
    if rec.get("error"):
        print(f"         error: {str(rec['error'])[:300]}")
    print(f"         dir: {rec.get('run_dir')}")


def cmd_openai(args: argparse.Namespace) -> int:
    from openai_batch import run_openai_mode, run_openai_sequential_baseline

    api_key = require_key("OPENAI_API_KEY")
    prompt = load_prompt(Path(args.prompt) if args.prompt else None)
    logo = default_logo_path()
    model = args.model
    size = args.size
    results: list[dict] = []

    if args.sequential:
        print(f"\n== OpenAI sequential baseline ({model}, n=1 x {args.count}) ==")
        results.append(
            run_openai_sequential_baseline(
                api_key=api_key,
                model=model,
                mode=args.mode,
                count=args.count,
                prompt=prompt,
                logo_path=logo,
                size=size,
            )
        )
    else:
        print(f"\n== OpenAI batch ({model}, mode={args.mode}, n={args.count}) ==")
        results.append(
            run_openai_mode(
                api_key=api_key,
                model=model,
                mode=args.mode,
                count=args.count,
                prompt=prompt,
                logo_path=logo,
                size=size,
            )
        )
        if args.compare_sequential:
            print(f"\n== OpenAI sequential comparison ==")
            results.append(
                run_openai_sequential_baseline(
                    api_key=api_key,
                    model=model,
                    mode=args.mode,
                    count=args.count,
                    prompt=prompt,
                    logo_path=logo,
                    size=size,
                )
            )

    for rec in results:
        _print_record(rec)

    summary_path = _HERE / "output" / "last_openai_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0 if all(not r.get("error") for r in results) else 1


def cmd_gemini(args: argparse.Namespace) -> int:
    from gemini_batch import run_gemini_strategy

    api_key = require_key("GOOGLE_API_KEY")
    prompt = load_prompt(Path(args.prompt) if args.prompt else None)
    logo = default_logo_path()
    strategies = args.strategies or ["image_only", "text_and_image"]
    if args.include_candidate_count:
        strategies.append("candidate_count")

    results: list[dict] = []
    for strategy in strategies:
        print(f"\n== Gemini ({args.model}, strategy={strategy}, count={args.count}) ==")
        rec = run_gemini_strategy(
            api_key=api_key,
            model=args.model,
            strategy=strategy,
            count=args.count,
            prompt=prompt,
            logo_path=logo,
            aspect_ratio=args.aspect,
            image_size=args.image_size if args.model == "gemini-3-pro-image-preview" else None,
        )
        results.append(rec)
        _print_record(rec)

    summary_path = _HERE / "output" / "last_gemini_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0 if any((r.get("images_saved") or 0) >= args.count for r in results) else 1


def cmd_all(args: argparse.Namespace) -> int:
    args.compare_sequential = True
    args.sequential = False
    args.include_candidate_count = args.include_candidate_count or False
    g = argparse.Namespace(**{**vars(args), "strategies": ["image_only", "text_and_image"]})
    code_g = cmd_gemini(g)
    code_o = cmd_openai(args)
    print("\n== Summary ==")
    print("  Gemini: see output/last_gemini_summary.json")
    print("  OpenAI: see output/last_openai_summary.json")
    return min(code_g, code_o)


def main() -> int:
    bootstrap_paths()
    parser = argparse.ArgumentParser(description="Multi-image generation experiments")
    sub = parser.add_subparsers(dest="command", required=True)

    p_openai = sub.add_parser("openai", help="OpenAI Images API (n parameter)")
    p_openai.add_argument("--count", type=int, default=3, help="Requested images (n)")
    p_openai.add_argument("--model", default="gpt-image-1-mini")
    p_openai.add_argument(
        "--mode",
        choices=("generate", "edit_reference"),
        default="edit_reference",
        help="generate=text-only; edit_reference=logo reference (like production)",
    )
    p_openai.add_argument("--size", default="1024x1024")
    p_openai.add_argument("--prompt", default="", help="Prompt file path")
    p_openai.add_argument("--sequential", action="store_true", help="N calls with n=1")
    p_openai.add_argument(
        "--compare-sequential",
        action="store_true",
        help="After batch, also run sequential baseline",
    )
    p_openai.set_defaults(func=cmd_openai)

    p_gemini = sub.add_parser("gemini", help="Gemini generateContent strategies")
    p_gemini.add_argument("--count", type=int, default=3)
    p_gemini.add_argument("--model", default="gemini-2.5-flash-image")
    p_gemini.add_argument("--aspect", default="1:1")
    p_gemini.add_argument("--image-size", default="2K", dest="image_size")
    p_gemini.add_argument("--prompt", default="")
    p_gemini.add_argument(
        "--strategies",
        nargs="*",
        choices=("image_only", "text_and_image", "candidate_count"),
        help="Which strategies to run",
    )
    p_gemini.add_argument(
        "--include-candidate-count",
        action="store_true",
        help="Also try candidateCount=N (often fails)",
    )
    p_gemini.set_defaults(func=cmd_gemini)

    p_all = sub.add_parser("all", help="Run OpenAI batch + Gemini strategies")
    p_all.add_argument("--count", type=int, default=2)
    p_all.add_argument("--model", default="gpt-image-1-mini")
    p_all.add_argument("--mode", default="edit_reference")
    p_all.add_argument("--size", default="1024x1024")
    p_all.add_argument("--prompt", default="")
    p_all.add_argument("--include-candidate-count", action="store_true")
    p_all.set_defaults(func=cmd_all)

    args = parser.parse_args()
    if args.command == "openai" and not hasattr(args, "compare_sequential"):
        args.compare_sequential = False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
