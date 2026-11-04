"""Apply the LAMP GSE6462 recipe to the historical inputs and validate the pair."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


def run(reference, command, *args):
    subprocess.run([sys.executable, "-B", str(reference / (command + ".py")), *map(str, args)],
                   check=True)


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        return next(reader), list(reader)


def validated(items, labels):
    header, features = read(items)
    _, targets = read(labels)
    labels_by_id = {}
    for identifier, label in targets:
        if identifier in labels_by_id or label not in {"0", "1"}:
            raise ValueError("duplicate ID or nonbinary label")
        labels_by_id[identifier] = label
    ids = [row[0] for row in features]
    if len(set(ids)) != len(ids) or set(ids) != labels_by_id.keys():
        raise ValueError("item and label IDs do not form a unique aligned pair")
    if any(len(row) != len(header) or set(row[1:]) - {"0", "1"} for row in features):
        raise ValueError("invalid binary feature matrix")
    ordered = [(i, labels_by_id[i]) for i in ids]
    dimensions = (len(ids), len(header) - 1, sum(label == "1" for _, label in ordered))
    return header, features, ordered, dimensions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("geo_matrix_gz", type=Path)
    parser.add_argument("affymetrix_na32_csv", type=Path)
    parser.add_argument("msigdb_v3_entrez_gmt", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    for path in (args.geo_matrix_gz, args.affymetrix_na32_csv, args.msigdb_v3_entrez_gmt):
        if not path.is_file():
            parser.error(f"missing input {path}")
    args.out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.out) as directory:
        temp = Path(directory)
        matrix = temp / "matrix.txt"
        with gzip.open(args.geo_matrix_gz, "rb") as source, matrix.open("wb") as output:
            shutil.copyfileobj(source, output)
        annotated = temp / "annotated.csv"
        ratios = temp / "ratios.csv"
        items = temp / "items.csv"
        merged = temp / "merged.csv"
        flags = temp / "flags.csv"
        run(args.reference, "convert_id", args.affymetrix_na32_csv, matrix, annotated)
        run(args.reference, "exp2ratio", "-t", 12, annotated, ratios)
        run(args.reference, "ratio2flag", ratios, 1.0, flags)
        run(args.reference, "gsea4csv", args.msigdb_v3_entrez_gmt, items)
        run(args.reference, "merge_exp_csv", ratios, items, merged)
        header, features, labels, dimensions = validated(merged, flags)
        if dimensions != (12773, 397, 1129):
            raise ValueError(f"observed {dimensions}; expected (12773, 397, 1129) for LAMP")
        for name, first, rows in (("items.csv", header, features),
                                  ("labels.csv", ["#id", "class"], labels)):
            with (args.out / name).open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file, lineterminator="\n")
                writer.writerow(first)
                writer.writerows(rows)
        print(json.dumps(dict(objects=dimensions[0], features=dimensions[1],
                              positives=dimensions[2])))


if __name__ == "__main__":
    main()
