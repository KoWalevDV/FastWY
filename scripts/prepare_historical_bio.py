"""Verify and materialize the historical input files preserved in LAMP Git history."""
import argparse
import csv
from pathlib import Path


def lcm_rows(path):
    # Empty transactions are real observations and preserve the sample size.
    return [tuple(sorted(map(int, row.split()))) for row in path.read_text(encoding="ascii").splitlines()]


def write_labels(path, rows):
    with path.open("w", newline="", encoding="ascii") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(("#id", "class"))
        writer.writerows(rows)


def yeast(data, out):
    with (data / "yeast_heatshock_target.csv").open(newline="", encoding="ascii") as file:
        reader = csv.reader(file)
        header = next(reader)
        matrix = list(reader)
    with (data / "yeast_heatshock_expression.tab").open(newline="", encoding="ascii") as file:
        records = list(csv.reader(file, delimiter="\t"))
    labels = dict((name, int(value)) for name, value in records)
    names = [row[0] for row in matrix]
    if len(matrix) != 6074 or len(labels) != len(records) or set(names) != labels.keys():
        raise ValueError("unexpected yeast genes")
    if len(set(names)) != len(names) or len(header) != 103 or set(labels.values()) != {0, 1}:
        raise ValueError("unexpected yeast columns or labels")
    if sum(labels.values()) != 530 or any(len(row) != len(header) or set(row[1:]) - {"0", "1"}
                                          for row in matrix):
        raise ValueError("unexpected yeast binary matrix")
    sorted_matrix = sorted(matrix, key=lambda row: labels[row[0]])
    encoded = [tuple(i for i, value in enumerate(row[1:], 1) if value == "1")
               for row in sorted_matrix]
    if encoded != lcm_rows(data / "yeast_tfsite.4lcmlamp.txt"):
        raise ValueError("2012 yeast source does not match the 2014 LCM fixture")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "items.csv").open("w", newline="", encoding="ascii") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(sorted_matrix)
    write_labels(out / "labels.csv", ((row[0], labels[row[0]]) for row in sorted_matrix))
    print("yeast: all 6074 rows match; 102 named motifs and 530 explicit positive labels")


def human(data, out):
    rows = lcm_rows(data / "gse6462_item.4lcmlamp.txt")
    columns = set().union(*(set(row) for row in rows))
    if len(rows) != 12773 or columns != set(range(1, 398)):
        raise ValueError("unexpected historical GSE6462 fixture shape")
    ids = [f"row-{i:05d}" for i in range(1, len(rows) + 1)]
    boundary = len(rows) - 1129
    out.mkdir(parents=True, exist_ok=True)
    with (out / "items.csv").open("w", newline="", encoding="ascii") as file:
        file.write("#id," + ",".join(f"motif-{i:03d}" for i in sorted(columns)) + "\n")
        for name, row in zip(ids, rows):
            fields = ["0"] * 397
            for index in row:
                fields[index - 1] = "1"
            file.write(name + "," + ",".join(fields) + "\n")
    write_labels(out / "labels.csv", ((name, int(i >= boundary)) for i, name in enumerate(ids)))
    print("GSE6462: 12773 ordered rows and 397 numeric motifs; 1129 inferred positive labels")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historical_inputs", type=Path)
    parser.add_argument("experiments", type=Path)
    args = parser.parse_args()
    yeast(args.historical_inputs, args.experiments / "11-yeast-historical")
    human(args.historical_inputs, args.experiments / "12-gse6462-historical")


if __name__ == "__main__":
    main()
