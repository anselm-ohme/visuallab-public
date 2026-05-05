"""Verify + fix the hard-coded Met image URLs in build_examples.py.

The original build_examples.py used guessed image URLs based on a URL
pattern observed in a few Met records. Met's actual filenames are not
predictable from the objectID, so many of those guesses 404. This script:

  1. Fetches the live Met API for each art-example objectID
  2. Reads back the canonical primaryImage URL
  3. Patches build_examples.py in-place so future regenerations get it right
  4. Re-runs build_examples.py to regenerate the static HTMLs

Usage from repo root:
    python scripts/fix_met_image_urls.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD_PY = ROOT / "scripts" / "build_examples.py"
MET_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


def load_art_data() -> list[dict]:
    """Import build_examples.ART_DATA without running main()."""
    spec = importlib.util.spec_from_file_location("build_examples_module", BUILD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ART_DATA


def fetch_met_primary(object_id: str) -> dict:
    r = requests.get(f"{MET_BASE}/objects/{object_id}", timeout=15)
    r.raise_for_status()
    return r.json()


def main() -> None:
    art_data = load_art_data()
    src = BUILD_PY.read_text(encoding="utf-8")
    changes = []
    issues = []

    for d in art_data:
        oid = d["object_id"]
        slug = d["slug"]
        old_url = d["image"]
        try:
            obj = fetch_met_primary(oid)
        except Exception as exc:
            issues.append((slug, f"Met fetch failed: {exc}"))
            continue
        new_url = obj.get("primaryImage") or ""
        thumb = obj.get("primaryImageSmall") or ""

        if not new_url:
            # Object has no public image (e.g. rights-restricted). Pick a
            # different well-known objectID; warn loudly.
            issues.append((slug, f"objectID {oid} has no primaryImage; may need replacement"))
            continue

        if new_url == old_url:
            print(f"[ ok ] {slug}: URL already correct")
            continue

        # Surgical in-place replacement of just this slug's image URL.
        # Anchor on the slug + image key so we never touch the wrong record.
        # Match the slug block, then within it replace ONE image: line.
        slug_pattern = re.compile(
            r'("slug":\s*"' + re.escape(slug) + r'",.*?"image":\s*)"[^"]*"',
            re.DOTALL,
        )
        new_src, n = slug_pattern.subn(rf'\1"{new_url}"', src, count=1)
        if n != 1:
            issues.append((slug, "could not locate slug+image block in source"))
            continue
        src = new_src
        changes.append((slug, old_url, new_url))
        print(f"[fix ] {slug}: {old_url} -> {new_url}")

    if changes:
        BUILD_PY.write_text(src, encoding="utf-8")
        print(f"\nPatched {len(changes)} image URLs in {BUILD_PY.name}")
    else:
        print("\nNo source changes needed.")

    if issues:
        print("\n--- ISSUES ---")
        for slug, msg in issues:
            print(f"  {slug}: {msg}")

    # Regenerate the HTML files now that the source is correct.
    print("\nRegenerating example HTML files…")
    spec = importlib.util.spec_from_file_location("build_examples_rerun", BUILD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()


if __name__ == "__main__":
    main()
