"""Prepare the pinned author sources to run on Windows with Python 3.12 and GCC."""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

ARCHIVE_SHA256 = "95060b2ffdd7b6eb82d9be8094d0feb337dafd9024b1e93b37c907bf775cf801"


def rewrite(path, replacements=(), normalize_indent=False):
    source = path.read_text(encoding="utf-8")
    for before, after in replacements:
        if before not in source:
            raise ValueError(f"{path}: expected source fragment missing")
        source = source.replace(before, after)
    if normalize_indent:
        source = source.replace(" \t", "\t").expandtabs(8)
    path.write_text(source, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("unexpected author archive SHA-256")
    args.destination.mkdir(parents=True)
    with ZipFile(args.archive) as archive:
        root_name = archive.namelist()[0].rstrip("/")
        archive.extractall(args.destination)
    root = args.destination / root_name
    subprocess.run([sys.executable, "-m", "lib2to3", "-w", "-n", "fastwy.py", "lamp.py",
                    "readFile.py", "frepattern", "functions"], cwd=root, check=True)
    rewrite(root / "fastwy.py", [
        ("cmp = lambda x,y:cmp(x[0], y[0])", "key = lambda x: x[0]"),
        ("enrich_lst.sort(lambda x,y:cmp(x[1], y[1]))", "enrich_lst.sort(key=lambda x: x[1])"),
    ], normalize_indent=True)
    rewrite(root / "transaction.py", normalize_indent=True)
    rewrite(root / "readFile.py", [("'rU'", "'r'")])
    subprocess.run(["gcc", "-O3", "-Os", "-s", "-o", "lcm53/lcm.exe", "lcm53/lcm.c", "-lm"],
                   cwd=root, check=True)
    print(root)


if __name__ == "__main__":
    main()
