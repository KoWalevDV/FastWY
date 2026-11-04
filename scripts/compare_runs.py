"""Compare closed patterns and Fisher values from two runs on shared labels."""
import argparse
import json
import math
from decimal import Decimal
from pathlib import Path


def read_run(path, author):
    threshold = None
    patterns = {}
    declared = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith(("# Adjusted significance level: ", "# threshold=")):
            threshold = Decimal(line.split(": " if author else "=", 1)[1])
        if line.startswith(("# # of significant combinations: ", "# significant_patterns=")):
            declared = int(line.split(": " if author else "=", 1)[1])
        if author and line.startswith(("Time ", "[id]")):
            break
        fields = line.split("\t")
        if author and len(fields) == 7 and fields[0].isdigit():
            _, raw, adjusted, name, _, support, positives = fields
        elif not author and len(fields) == 6 and fields[1].isdigit():
            name, support, positives, raw, adjusted, _ = fields
        else:
            continue
        key = tuple(sorted(name.split(",")))
        if key in patterns:
            raise ValueError(f"{path}: duplicate pattern {key}")
        patterns[key] = (int(support), int(positives), Decimal(raw), adjusted)
    if threshold is None or declared != len(patterns):
        raise ValueError(f"{path}: incomplete output")
    return threshold, patterns


def compare(author_path, cpp_path, oracle=False):
    reference_threshold, reference = read_run(author_path, not oracle)
    source = "oracle" if oracle else "author"
    cpp_threshold, cpp = read_run(cpp_path, False)
    common = reference.keys() & cpp.keys()
    underflows = 0
    raw_mismatches = 0
    count_mismatches = 0
    adjusted_mismatches = 0
    for pattern in common:
        ref_support, ref_positive, ref_p, ref_adj = reference[pattern]
        support, positive, p, adj = cpp[pattern]
        count_mismatches += (support, positive) != (ref_support, ref_positive)
        if ref_p == 0 and p > 0:
            underflows += 1
        else:
            raw_mismatches += abs(ref_p - p) > p * Decimal("0.00006")
        if ref_adj.startswith("<"):
            adjusted_mismatches += Decimal(adj) >= Decimal(ref_adj[1:].strip())
        else:
            adjusted_mismatches += not math.isclose(float(adj), float(ref_adj), rel_tol=6e-5)
    return {
        f"{source}_threshold": str(reference_threshold),
        "cpp_threshold": str(cpp_threshold),
        f"thresholds_match_to_{source}_precision": (
            abs(reference_threshold - cpp_threshold) <= cpp_threshold * Decimal("0.00006")
        ),
        f"{source}_patterns": len(reference),
        "cpp_patterns": len(cpp),
        "common_patterns": len(common),
        f"{source}_only": len(reference.keys() - cpp.keys()),
        "cpp_only": len(cpp.keys() - reference.keys()),
        "support_or_positive_mismatches": count_mismatches,
        f"raw_p_mismatches_excluding_{source}_zeros": raw_mismatches,
        f"{source}_zero_raw_p_with_positive_cpp_p": underflows,
        "adjusted_p_mismatches": adjusted_mismatches,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--oracle", action="store_true")
    args = parser.parse_args()
    folder = args.experiment
    source = "oracle.tsv" if args.oracle else "author.tsv"
    print(json.dumps(compare(folder / source, folder / "cpp.tsv", args.oracle), indent=2))
