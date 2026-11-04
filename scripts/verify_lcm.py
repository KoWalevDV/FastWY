"""Verify C++ with author LCM and an independent exhaustive minP calculation."""
import argparse
from bisect import bisect_left, bisect_right
import csv
from functools import lru_cache
import math
import os
from pathlib import Path
import random
import subprocess

EPSILON = 2e-10


def pack(rows, size):
    packed = bytearray((size + 7) // 8)
    for row in rows:
        packed[row // 8] |= 1 << (row % 8)
    return int.from_bytes(packed, "little")


def load_labels(path):
    with path.open(newline="", encoding="ascii") as source:
        reader = csv.reader(source)
        next(reader)
        return [(row[0], int(row[1])) for row in reader]


def generate(labels, path, count, seed):
    rng = random.Random(seed)
    positions = list(range(len(labels)))
    positive = sum(labels)
    with path.open("w", newline="", encoding="ascii") as out:
        writer = csv.writer(out, lineterminator="\n")
        for _ in range(count):
            selected = sorted(rng.sample(positions, positive))
            row = bytearray(len(labels))
            for i in selected:
                row[i] = 1
            writer.writerow(row)
            yield pack(selected, len(labels))


def prepare_transactions(path, destination):
    with path.open(newline="", encoding="ascii") as source, destination.open("w") as target:
        reader = csv.reader(source)
        names = next(reader)[1:]
        ids = []
        for row in reader:
            ids.append(row[0])
            target.write(" ".join(str(i) for i, value in enumerate(row[1:], 1) if value == "1"))
            target.write("\n")
    return names, ids


def log_choose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def make_fisher(size, positive):
    negative = size - positive

    @lru_cache(maxsize=None)
    def tails(support):
        lo = max(0, support - negative)
        hi = min(support, positive)
        mass = log_choose(positive, hi) + log_choose(negative, support - hi) - log_choose(size, support)
        tail = [mass]
        for a in range(hi, lo, -1):
            mass += math.log((a * (negative - support + a)) /
                             ((positive - a + 1) * (support - a + 1)))
            current = tail[-1]
            tail.append(max(current, mass) + math.log1p(math.exp(-abs(current - mass))))
        tail[-1] = 0.0
        return lo, tail[::-1]

    return tails


def calculate(patterns, names, labels, permutations, minimum, output):
    size = len(labels)
    positive = sum(labels)
    fisher = make_fisher(size, positive)
    original = pack((i for i, label in enumerate(labels) if label), size)
    minima = [0.0] * len(permutations)
    potential = []
    max_minimum = 0.0
    with patterns.open(encoding="ascii") as records:
        for header in records:
            coverage_row = next(records)
            fields = header.split()
            if len(fields) == 1:  # Empty pattern has no hypothesis.
                continue
            members = list(map(int, coverage_row.split()))
            support = len(members)
            if support < minimum or support != int(fields[-1].strip("()")):
                raise ValueError("LCM support or output format mismatch")
            lo, tail = fisher(support)
            attainable = tail[-1]
            if attainable > max_minimum:
                continue
            coverage = pack(members, size)
            a = (coverage & original).bit_count()
            observed = tail[a - lo]
            if observed <= math.log(0.05):
                pattern = ",".join(names[i - 1] for i in sorted(map(int, fields[:-1])))
                potential.append((observed, pattern, support, a))
            for j, labels_j in enumerate(permutations):
                if minima[j] > attainable:
                    permuted = tail[(coverage & labels_j).bit_count() - lo]
                    if permuted < minima[j]:
                        minima[j] = permuted
            # Keep only a cheap upper bound during enumeration.
            if support % 32 == 0:
                max_minimum = max(max(minima), math.log(0.05))

    minima.sort()
    budget = len(minima) // 20
    cut = bisect_left(minima, minima[budget] - EPSILON)
    threshold = minima[cut - 1] if cut else -math.inf
    omitted = fisher(minimum - 1)[1][-1] if minimum > 1 else math.inf
    if minimum > positive or omitted <= minima[budget] + EPSILON:
        raise ValueError("Support cutoff does not certify the threshold; lower --minimum")

    def scientific(log_p):
        if log_p == math.inf:
            return "inf"
        if log_p == -math.inf:
            return "0"
        exponent = math.floor(log_p / math.log(10))
        return f"{math.exp(log_p - exponent * math.log(10)):.12g}e{exponent}"

    findings = [(p, name, s, a, bisect_right(minima, p + EPSILON))
                for p, name, s, a in potential if p <= threshold + EPSILON]
    with output.open("w", encoding="ascii", newline="") as result:
        print(f"# alpha=0.05\n# permutations={len(minima)}\n# threshold={scientific(threshold)}"
              f"\n# significant_patterns={len(findings)}", file=result)
        print("pattern\tsupport\tpositives\tp_raw\tp_adjusted\tadjusted_count", file=result)
        for p, name, support, a, count in sorted(findings):
            print(name, support, a, scientific(p), f"{count / len(minima):.12g}", count,
                  sep="\t", file=result)
    print(f"Cutoff certified: omitted patterns have p >= {scientific(omitted)};"
          f" rank B/20 + 1 = {scientific(minima[budget])}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lcm", type=Path)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("scratch", type=Path)
    parser.add_argument("--minimum", type=int, default=16)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 20 <= args.count <= 10000 or args.minimum < 1:
        parser.error("use 20..10000 permutations and a positive minimum support")
    args.scratch.mkdir(parents=True, exist_ok=True)
    transactions = args.scratch / "oracle-input.txt"
    patterns = args.scratch / "oracle-patterns.txt"
    names, ids = prepare_transactions(args.experiment / "items.csv", transactions)
    targets = load_labels(args.experiment / "labels.csv")
    if ids != [name for name, _ in targets] or len(set(ids)) != len(ids):
        raise ValueError("item and label IDs must be unique and have the same order")
    labels = [label for _, label in targets]
    if set(labels) != {0, 1} or args.minimum > sum(labels):
        raise ValueError("both classes are required and minimum may not exceed positive count")
    permutations = list(generate(labels, args.experiment / "permutations.csv",
                                 args.count, args.seed))
    subprocess.run([os.path.relpath(args.lcm), "CIf", os.path.relpath(transactions),
                    str(args.minimum), os.path.relpath(patterns)], check=True)
    calculate(patterns, names, labels, permutations, args.minimum, args.experiment / "oracle.tsv")


if __name__ == "__main__":
    main()
