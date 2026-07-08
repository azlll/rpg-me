#!/usr/bin/env python3
"""
Build the installable rpg-me.skill package.

The skill package is a zip archive with a .skill extension. Keep the file list
explicit so release artifacts do not accidentally include caches or local data.
"""

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = "rpg-me"
PACKAGE_FILES = [
    "README.md",
    "LICENSE",
    "VERSION",
    "SKILL.md",
    "assets/placeholder-portrait.svg",
    "assets/portrait-sample.png",
    "references/image-generation.md",
    "scripts/generate_portrait.py",
    "scripts/history_records.py",
    "scripts/package_skill.py",
    "scripts/render_sample_cards.py",
    "scripts/viewer_server.py",
    "scripts/card-template.html",
]


def package_skill(out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel_path in PACKAGE_FILES:
            source = ROOT / rel_path
            if not source.is_file():
                raise FileNotFoundError(f"Missing package file: {rel_path}")
            archive.write(source, f"{PACKAGE_ROOT}/{rel_path}")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Build dist/rpg-me.skill")
    parser.add_argument("--out", default=str(ROOT / "dist" / "rpg-me.skill"), help="Output .skill path")
    args = parser.parse_args()

    out_path = package_skill(args.out)
    print(f"PACKAGED: {out_path}")


if __name__ == "__main__":
    main()
