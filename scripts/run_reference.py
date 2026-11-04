"""Run a prepared Python 3 copy of author FastWY with shared permutations."""
import argparse
import csv
import random
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("items", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("permutations", type=Path)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()

    sys.path.insert(0, str(args.reference.resolve()))
    import fastwy

    with args.items.open(newline="", encoding="ascii") as file:
        reader = csv.reader(file)
        next(reader)
        ids = [row[0] for row in reader]
    original_permute = fastwy.permuteData
    random.seed(args.seed)
    with args.permutations.open("w", newline="", encoding="ascii") as file:
        writer = csv.writer(file, lineterminator="\n")

        def record(transactions, values):
            shuffled, mapping = original_permute(transactions, values)
            label_by_id = {item.name: int(shuffled[mapping[item.getID()]].value)
                           for item in transactions}
            writer.writerow(label_by_id[name] for name in ids)
            return shuffled, mapping

        fastwy.permuteData = record
        fastwy.run(args.items.as_posix(), args.labels.as_posix(), 0.05, args.count, "fisher",
                   args.reference.as_posix() + "/lcm53/lcm.exe", "all",
                   str(args.log), 1)


if __name__ == "__main__":
    main()

