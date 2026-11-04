"""Check GSE6462 ordering against the published LAMP example."""
import csv
from decimal import Decimal, localcontext
from math import comb, exp
from pathlib import Path

from verify_lcm import make_fisher


def fisher_exact(n, positives, support, count):
    total = sum(comb(positives, k) * comb(n - positives, support - k)
                for k in range(count, min(support, positives) + 1))
    with localcontext() as ctx:
        ctx.prec = 32
        return Decimal(total) / comb(n, support)


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("historical_matrix", type=Path)
    parser.add_argument("lcm_patterns", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    rows = [tuple(map(int, line.split())) for line in args.historical_matrix.read_text().splitlines()]
    n, positives = len(rows), 1129
    boundary = n - positives
    fisher = make_fisher(n, positives)
    published_cutoff = 0.05 / 3750336
    accepted = []
    checked = 0
    with args.lcm_patterns.open(encoding="ascii") as patterns:
        for header in patterns:
            coverage = next(patterns)
            fields = header.split()
            if len(fields) < 2:
                continue
            support = int(fields[-1].strip("()"))
            if support < 8:
                continue
            checked += 1
            lo, tail = fisher(support)
            if exp(tail[-1]) > published_cutoff:
                continue
            covered = list(map(int, coverage.split()))
            if len(covered) != support:
                raise ValueError("invalid LCM coverage")
            count = sum(row >= boundary for row in covered)
            if exp(tail[count - lo]) <= published_cutoff:
                exact = fisher_exact(n, positives, support, count)
                ids = tuple(sorted(int(motif) for motif in fields[:-1]))
                accepted.append((exact, ids, support, count))
    accepted.sort()
    fingerprints = [(len(ids), s, a, float(f"{p:.5g}")) for p, ids, s, a in accepted]
    expected = [(1, 957, 141, 3.7083e-10), (4, 10, 9, 2.9459e-9), (8, 8, 8, 3.6422e-9)]
    if fingerprints != expected:
        raise ValueError(f"LAMP fingerprint mismatch: {fingerprints}")
    with args.out.open("w", newline="", encoding="ascii") as target:
        writer = csv.writer(target, delimiter="\t", lineterminator="\n")
        writer.writerow(("motif_ids", "arity", "support", "positives", "exact_p"))
        for p, ids, support, count in accepted:
            writer.writerow((",".join(map(str, ids)), len(ids), support, count, p))
    print(f"{checked} closed patterns checked at support >= 8; all 3 published fingerprints match")


if __name__ == "__main__":
    main()
