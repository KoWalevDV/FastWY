"""Verify all files listed in an extracted experiment release."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    records = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected in records["sha256"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("manifest path escapes the bundle")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"checksum mismatch: {relative}")
    print(f"PASS: {len(records['sha256'])} experiment files")


if __name__ == "__main__":
    main()
