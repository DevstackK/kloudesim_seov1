#!/usr/bin/env python3
"""
Headless batch driver for KloudeSIM destination pages.

Runs `claude -p` once per destination so each page gets a fresh context
and a proper humanising pass. Use this for cron/CI runs; use the
/batch-generate slash command for interactive runs.

Usage:
    python scripts/generate_pages.py                # all missing destinations
    python scripts/generate_pages.py --region Asia  # filter by region
    python scripts/generate_pages.py --only japan turkey
    python scripts/generate_pages.py --force        # regenerate even if file exists

Requires: Claude Code installed and authenticated (`claude` on PATH).
"""

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRICING_CSV = ROOT / "data" / "kloudesim-pricing.csv"
OUTPUT_DIR = ROOT / "output"

PROMPT_TEMPLATE = (
    "Generate the KloudeSIM destination landing page for {country}. "
    "Use the kloudesim-destination-page skill and follow its full workflow: "
    "load pricing from data/kloudesim-pricing.csv and data/competitor-pricing.csv, "
    "read all three reference files, draft, run the humanising pass, complete the "
    "self-check, and save to output/esim-{slug}.md. "
    "Never invent prices or coverage facts. "
    "Finish by printing the saved file path and any [NEEDS DATA] flags."
)


def load_destinations(region: str | None) -> dict[str, str]:
    """Return {slug: country} for unique destinations, optionally filtered by region."""
    destinations: dict[str, str] = {}
    with open(PRICING_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if region and row["region"].strip().lower() != region.lower():
                continue
            destinations[row["country_slug"].strip()] = row["country"].strip()
    return destinations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", help="only this region (e.g. Asia)")
    parser.add_argument("--only", nargs="*", help="only these country slugs")
    parser.add_argument("--force", action="store_true", help="regenerate existing pages")
    parser.add_argument("--model", default=None, help="model override for claude -p")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    destinations = load_destinations(args.region)

    if args.only:
        destinations = {s: c for s, c in destinations.items() if s in set(args.only)}

    todo = {
        slug: country
        for slug, country in destinations.items()
        if args.force or not (OUTPUT_DIR / f"esim-{slug}.md").exists()
    }

    if not todo:
        print("Nothing to generate — all destination pages exist. Use --force to regenerate.")
        return 0

    print(f"Generating {len(todo)} page(s): {', '.join(todo.values())}\n")

    failures = []
    for slug, country in todo.items():
        print(f"--- {country} ({slug}) ---")
        cmd = ["claude", "-p", PROMPT_TEMPLATE.format(country=country, slug=slug),
               "--allowedTools", "Read,Write,Edit,Glob,Grep"]
        if args.model:
            cmd += ["--model", args.model]
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES"}
        result = subprocess.run(cmd, cwd=ROOT, env=env)
        if result.returncode != 0 or not (OUTPUT_DIR / f"esim-{slug}.md").exists():
            failures.append(country)
            print(f"!! {country} failed or produced no output file\n")
        else:
            print(f"ok: output/esim-{slug}.md\n")

    print(f"Done. {len(todo) - len(failures)}/{len(todo)} succeeded.")
    if failures:
        print(f"Failed: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
