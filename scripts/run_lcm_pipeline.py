"""Run LCM enumeration and the C++ statistical pass as one measured process tree."""
import argparse
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lcm", type=Path)
    parser.add_argument("evaluator", type=Path)
    parser.add_argument("items", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("lcm_input", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--support", type=int, default=7)
    parser.add_argument("--permutations", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    patterns = args.work / "patterns.txt"
    with (args.work / "lcm.stdout").open("wb") as output, (
        args.work / "lcm.stderr"
    ).open("wb") as error:
        subprocess.run([str(args.lcm.resolve()), "CIf", str(args.lcm_input.resolve()),
                        str(args.support), str(patterns.resolve())],
                       stdout=output, stderr=error, check=True)
    permutation_args = ["--permutation-file", str(args.permutations.resolve())] if args.permutations else [
        str(args.count), str(args.seed)
    ]
    subprocess.run([str(args.evaluator.resolve()), str(args.items.resolve()),
                    str(args.labels.resolve()), str(patterns.resolve()), str(args.support),
                    *permutation_args], check=True)


if __name__ == "__main__":
    main()
