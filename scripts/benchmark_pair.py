"""Repeat a paired author/C++ experiment on identical recorded permutations."""
import argparse
import csv
from pathlib import Path
import shutil
import sys

from compare_runs import compare
from measure_windows import measure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("program", type=Path)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("scratch", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.scratch.mkdir(parents=True, exist_ok=True)
    items = args.scratch / "items.csv"
    labels = args.scratch / "labels.csv"
    shutil.copyfile(args.experiment / "items.csv", items)
    shutil.copyfile(args.experiment / "labels.csv", labels)
    permutations = args.experiment / "permutations.csv"
    fields = ["run", "implementation", "permutations", "seed", "elapsed_seconds",
              "peak_tree_commit_bytes"]
    with (args.experiment / "measurements.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for run in range(1, args.repeats + 1):
            author_output = args.experiment / f"author-{run}.tsv"
            cpp_output = args.experiment / f"cpp-{run}.tsv"
            author = [sys.executable, "-B", "scripts/run_reference.py", str(args.reference),
                      str(items), str(labels), str(permutations), "--count", str(args.count),
                      "--seed", str(args.seed), "--log", str(args.scratch / f"author-{run}.log")]
            cpp = [str(args.program.resolve()), str(items), str(labels),
                   "--permutation-file", str(permutations)]
            for name, command, output in (("author", author, author_output), ("cpp", cpp, cpp_output)):
                metrics = measure(command, output, args.scratch / f"{name}-{run}.err")
                writer.writerow(dict(run=run, implementation=name, permutations=args.count,
                                     seed=args.seed, **metrics))
                out.flush()
                print(name, run, metrics, flush=True)
            verdict = compare(author_output, cpp_output)
            if not verdict["thresholds_match_to_author_precision"] or any(
                verdict[name] for name in ("author_only", "cpp_only", "support_or_positive_mismatches")
            ):
                raise ValueError(f"run {run} failed comparison: {verdict}")


if __name__ == "__main__":
    main()
