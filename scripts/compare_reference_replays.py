"""Compare two author outputs, excluding timers and filesystem paths."""
import json
from pathlib import Path
import sys

from compare_runs import read_run


def minima(path):
    rows = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("[") and not line.startswith("[id]"):
            fields = line.split("\t")
            rows[fields[0]] = fields[1:4] + fields[6:7]
    return rows


def main():
    first, second = map(Path, sys.argv[1:3])
    if read_run(first, True) != read_run(second, True):
        raise ValueError("threshold or findings differ")
    first_minima = minima(first)
    if not first_minima or first_minima != minima(second):
        raise ValueError("minP, stopping support, or candidates differ")
    print(json.dumps({"identical_threshold_findings_minima_supports_candidates": True,
                      "permutations": len(first_minima)}))


if __name__ == "__main__":
    main()
