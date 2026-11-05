"""Recover historical biological inputs from the public LAMP Git repository."""
import argparse
import hashlib
from pathlib import Path
import subprocess

FILES = {
    "yeast_heatshock_expression.tab": ("761075c14b7d0fcceca29619e221334fbdf9f6c8", "7edf2154a7da7daff1abe91edc41704794e8f687217d54245d5b471f518ead6a"),
    "yeast_heatshock_target.csv": ("761075c14b7d0fcceca29619e221334fbdf9f6c8", "ce6b90c9d295affd22699dbda1d3918dc58d21acb1545758bc06384881faeedd"),
    "yeast_tfsite.4lcmlamp.txt": ("5aeb0867717881afe8ba72cfb2b5047cf6aaa180", "4d8955903b0f6d40189883ec85cbea0e54835163715250794753b51638c3de45"),
    "gse6462_item.4lcmlamp.txt": ("5aeb0867717881afe8ba72cfb2b5047cf6aaa180", "68e67c49a7f6264069083356f181ef25ddce3ee52951e030e3228e710200eb54"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mirror", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not args.mirror.exists():
        subprocess.run(["git", "clone", "--mirror", "https://github.com/a-terada/lamp.git",
                        str(args.mirror)], check=True)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, (revision, expected) in FILES.items():
        result = subprocess.check_output(["git", "-C", str(args.mirror), "show",
                                          f"{revision}:sample/{name}"])
        if hashlib.sha256(result).hexdigest() != expected:
            raise ValueError(f"historical hash mismatch: {name}")
        (args.output / name).write_bytes(result)
        print(name, expected)


if __name__ == "__main__":
    main()
