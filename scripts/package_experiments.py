"""Create an experiment release with hashes and pinned upstream sources."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("staging", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stage = args.staging.resolve()
    if args.archive.resolve().is_relative_to(stage):
        parser.error("archive must be outside staging")
    source = root / "experiments"
    shutil.copytree(source, stage / "experiments", dirs_exist_ok=True)
    for path in (stage / "experiments").rglob("*"):
        if not path.is_file():
            continue
        if path.stat().st_size == 0:
            path.unlink()
            continue
        if path.suffix.lower() not in {".tsv", ".log", ".txt", ".md", ".stderr", ".json"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = path.read_text(encoding="cp1251")
        text = text.replace(str(root), "<project>").replace(root.as_posix(), "<project>")
        text = re.sub(r"(?m)^Computer:.*$", "Computer: local verification host", text)
        path.write_text(text, encoding="utf-8")
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                       text=True).strip()
    records = {}
    for path in sorted(stage.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            records[path.relative_to(stage).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (stage / "manifest.json").write_text(json.dumps(
        {"source_commit": revision, "sha256": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with ZipFile(args.archive, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(stage).as_posix())
    print(revision, len(records), args.archive)


if __name__ == "__main__":
    main()
