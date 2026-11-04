"""Check the toy matrix under exchangeable labels with a fixed positive count."""
import argparse
import csv
import json
import math
from pathlib import Path
import random
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--trials", type=int, default=500)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    items = Path("data/sample_item.csv")
    with Path("data/sample_expression_over1.csv").open(newline="") as source:
        header, *records = csv.reader(source)
    count = sum(int(value) for _, value in records)
    rng = random.Random(314159)
    events = 0
    labels = args.output / "labels-last.csv"
    with (args.output / "trials.csv").open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["trial", "permutation_seed", "null_labels", "threshold", "findings"])
        for trial in range(1, args.trials + 1):
            positive = set(rng.sample(range(len(records)), count))
            flags = [int(index in positive) for index in range(len(records))]
            with labels.open("w", newline="") as target:
                label_writer = csv.writer(target)
                label_writer.writerow(header)
                label_writer.writerows((name, flag) for (name, _), flag in zip(records, flags))
            seed = rng.randrange(2**32)
            result = subprocess.check_output(
                [str(args.program.resolve()), str(items), str(labels), "1000", str(seed)],
                text=True,
            ).splitlines()
            threshold = next(line.split("=")[-1].strip() for line in result if "threshold" in line)
            findings = sum(bool(line) and not line.startswith("#") for line in result) - 1
            if findings < 0:
                raise ValueError("Missing result header")
            events += findings > 0
            writer.writerow([trial, seed, "".join(map(str, flags)), threshold, findings])
    rate = events / args.trials
    z = 1.959963984540054
    denominator = 1 + z*z / args.trials
    center = (rate + z*z / (2*args.trials)) / denominator
    radius = z * math.sqrt(rate*(1-rate)/args.trials + z*z/(4*args.trials**2)) / denominator
    summary = {"trials": args.trials, "permutations_per_trial": 1000, "events": events,
               "rate": rate, "wilson_95": [center-radius, center+radius],
               "exact_full_permutation_fwer": 94 / 6435}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
