"""Repeat yeast timings with the same prerecorded permutations in both programs."""
import argparse
import csv
from pathlib import Path
import random
import re
import shutil
import sys

from compare_runs import compare
from measure_windows import measure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, choices=[1000, 2500, 5000, 10000], default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    source = Path("experiments/11-yeast-historical")
    output = Path("experiments/15-yeast-matched")
    if args.count != 1000:
        output /= str(args.count)
    scratch = Path("build/historical/yeast-matched") / str(args.count)
    output.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    for name in ("items.csv", "labels.csv"):
        shutil.copyfile(source / name, scratch / name)
    permutations = source / "permutations.csv"
    if args.count > 1000:
        with (source / "labels.csv").open(newline="") as label_file:
            rows = csv.reader(label_file)
            next(rows)
            labels = [row[1] for row in rows]
        permutations = scratch / "permutations.csv"
        shutil.copyfile(source / "permutations.csv", permutations)
        rng = random.Random(271828)
        with permutations.open("a", newline="") as file:
            writer = csv.writer(file)
            for _ in range(args.count - 1000):
                rng.shuffle(labels)
                writer.writerow(labels)
    with (output / "measurements.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["run", "implementation", "elapsed_seconds", "search_seconds",
                         "peak_tree_commit_bytes"])
        for run in range(1, args.repeats + 1):
            commands = {
                "author": [sys.executable, "-B", "scripts/replay_reference.py",
                           "build/reference/lamp-master", str(scratch), str(permutations),
                           str(scratch / f"author-{run}.log"), "--count", str(args.count)],
                "cpp": [str(Path("build/historical/timed_fastwy.exe").resolve()),
                        str(scratch / "items.csv"), str(scratch / "labels.csv"), str(permutations)],
            }
            order = ("author", "cpp") if run % 2 else ("cpp", "author")
            for name in order:
                stdout = output / f"{name}-{run}.tsv"
                stderr = output / f"{name}-{run}.log"
                metrics = measure(commands[name], stdout, stderr)
                if name == "author":
                    line = re.search(r"Enumerating significant combinations [\d.]+, Total ([\d.]+)",
                                     stdout.read_text(encoding="ascii"))
                else:
                    line = re.search(r"search_seconds=([\d.eE+-]+)", stderr.read_text(encoding="ascii"))
                if line is None:
                    raise ValueError(f"missing internal timer: {name}")
                writer.writerow([run, name, metrics["elapsed_seconds"], line[1],
                                 metrics["peak_tree_commit_bytes"]])
                file.flush()
            verdict = compare(output / f"author-{run}.tsv", output / f"cpp-{run}.tsv")
            if not verdict["thresholds_match_to_author_precision"] or any(
                verdict[key] for key in ("author_only", "cpp_only", "support_or_positive_mismatches")
            ):
                raise ValueError(f"paired results differ: {verdict}")


if __name__ == "__main__":
    main()
