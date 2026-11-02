#!/usr/bin/env python3
"""Build an MCP Bundle (.mcpb) from the project root.

Usage:
    python scripts/build_mcpb.py [--output-dir DIR] [--version VER]

The script reads manifest.json, validates required files, and creates a zip
named <name>-<version>.mcpb (lowercase name, dots → dashes) in the output dir.
"""

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

REQUIRED_FILES = [
    "manifest.json",
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "blender_mcp_plus/__init__.py",
]

def main() -> int:
    parser = argparse.ArgumentParser(description="Build .mcpb bundle")
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument("--version", help="Override version from manifest.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    os.chdir(root)

    with open("manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)

    name = manifest["name"].lower().replace(" ", "-")
    version = args.version or manifest["version"]
    mcpb_name = f"{name}-{version}.mcpb"

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / mcpb_name

    # Validate required files exist
    missing = [f for f in REQUIRED_FILES if not Path(f).exists()]
    if missing:
        print(f"Missing required files: {missing}", file=sys.stderr)
        return 1

    # Read .mcpbignore patterns
    ignore_patterns = []
    if Path(".mcpbignore").exists():
        with open(".mcpbignore", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ignore_patterns.append(line)

    def should_ignore(path: Path) -> bool:
        rel = path.as_posix()
        for pat in ignore_patterns:
            if pat.startswith("/*"):
                if Path(rel).match(pat[1:]):
                    return True
            elif pat.endswith("/"):
                if rel.startswith(pat) or "/" + pat in rel:
                    return True
            else:
                if Path(rel).match(pat):
                    return True
        return False

    # Build the zip
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in Path(".").rglob("*"):
            if file_path.is_file():
                if file_path.name == mcpb_name:
                    continue
                if should_ignore(file_path):
                    continue
                arcname = file_path.as_posix()
                zf.write(file_path, arcname)
                print(f"  + {arcname}")

    print(f"\nCreated: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")
    return 0

if __name__ == "__main__":
    sys.exit(main())