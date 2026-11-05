"""Compare the CLI with an independent exact enumeration on small matrices."""
import csv
from fractions import Fraction
from itertools import combinations
from math import comb, isclose
from pathlib import Path
import random
import subprocess
import sys
import tempfile


def write(path, rows):
    with path.open("w", newline="", encoding="ascii") as file:
        csv.writer(file).writerows(rows)


def check(program, directory, features, observed, n):
    names = [f"F{i}" for i in range(len(features))]
    ids = [f"R{i}" for i in range(n)]
    items, labels = directory / "items.csv", directory / "labels.csv"
    write(items, [["#id", *names], *[
        [name, *(int(i in feature) for feature in features)] for i, name in enumerate(ids)
    ]])
    write(labels, [["#id", "class"], *[[name, int(i in observed)] for i, name in enumerate(ids)]])
    output = subprocess.check_output([program, str(items), str(labels), "--exact"], text=True)
    header = dict(line[2:].split("=", 1) for line in output.splitlines() if line.startswith("# "))
    k = len(observed)

    def fisher(s, a):
        return Fraction(sum(comb(s, i) * comb(n - s, k - i)
                            for i in range(a, min(s, k) + 1)), comb(n, k))

    closed = {}
    for size in range(1, len(features) + 1):
        for subset in combinations(features, size):
            coverage = set.intersection(*map(set, subset))
            if coverage:
                key = ",".join(name for name, feature in zip(names, features) if coverage <= feature)
                closed[key] = coverage
    minima = [min((fisher(len(cover), len(cover.intersection(positive)))
                   for cover in closed.values()), default=Fraction(1))
              for positive in map(set, combinations(range(n), k))]
    budget = len(minima) // 20
    threshold = max((p for p in set(minima) if sum(m <= p for m in minima) <= budget),
                    default=Fraction())
    assert isclose(float(header["threshold"]), float(threshold), rel_tol=1e-10)
    expected = {}
    for pattern, cover in closed.items():
        positive = len(cover & observed)
        p = fisher(len(cover), positive)
        if p <= threshold:
            expected[pattern] = len(cover), positive, p, sum(m <= p for m in minima)
    records = list(csv.DictReader((line for line in output.splitlines()
                                   if not line.startswith("#")), delimiter="\t"))
    assert len(records) == len(expected) == int(header["significant_patterns"])
    for record in records:
        support, positive, p, adjusted = expected.pop(record["pattern"])
        assert (int(record["support"]), int(record["positives"])) == (support, positive)
        assert isclose(float(record["p_raw"]), float(p), rel_tol=1e-10)
        assert int(record["adjusted_count"]) == adjusted
    return len(records)


def main():
    program = str(Path(sys.argv[1]).resolve())
    rng = random.Random(5807)
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        discoveries = check(program, directory, [{0, 1, 2}] * 2 + [set(range(8))], {0, 1, 2}, 8)
        for _ in range(24):
            n = rng.randint(7, 10)
            features = [{i for i in range(n) if rng.random() < 0.4} for _ in range(5)]
            observed = set(rng.sample(range(n), rng.randrange(2, n - 1)))
            discoveries += check(program, directory, features, observed, n)
        assert discoveries > 0
        labels = directory / "labels.csv"
        for bad in ("#id,class\nwrong,1\n", "#id,class\nR0,2\n"):
            labels.write_text(bad, encoding="ascii")
            failure = subprocess.run([program, str(directory / "items.csv"), str(labels), "--exact"],
                                     capture_output=True)
            assert failure.returncode != 0 and failure.stderr
    print("PASS: 25 exact oracle cases and invalid CSV inputs")


if __name__ == "__main__":
    main()
