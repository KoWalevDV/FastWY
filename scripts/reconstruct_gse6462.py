"""Rebuild GSE6462 using public GPL570 and MSigDB v6, following the LAMP recipe."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from prepare_gse6462 import run, validated


def adapt_probe_map(archive, out):
    with gzip.open(archive, "rt", encoding="latin-1", newline="") as source, (
        out.open("w", encoding="ascii", newline="")
    ) as output:
        for line in source:
            if line.startswith("ID\t"):
                header = line.rstrip("\r\n").split("\t")
                break
        else:
            raise ValueError("GPL570 header not found")
        gene_index = header.index("Gene ID")
        writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\n")
        for row in source:
            fields = row.rstrip("\r\n").split("\t")
            if len(fields) <= gene_index:
                continue
            ids = [item.strip() for item in fields[gene_index].split("///") if item.strip().isdigit()]
            if ids:
                writer.writerow([fields[0], *[""] * 17, " /// ".join(ids)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.out) as directory:
        temp = Path(directory)
        matrix = temp / "matrix.txt"
        mapping = temp / "probe_to_entrez.csv"
        with gzip.open(args.source / "GSE6462_series_matrix.txt.gz", "rb") as source, matrix.open("wb") as out:
            shutil.copyfileobj(source, out)
        adapt_probe_map(args.source / "GPL570.annot.gz", mapping)
        annotated, ratios, items, merged, flags = [
            temp / name for name in ("annotated.csv", "ratios.csv", "items.csv", "merged.csv", "flags.csv")
        ]
        run(args.reference, "convert_id", mapping, matrix, annotated)
        run(args.reference, "exp2ratio", "-t", 12, annotated, ratios)
        run(args.reference, "ratio2flag", ratios, 1.0, flags)
        run(args.reference, "gsea4csv", args.source / "c3.tft.v6.0.entrez.gmt", items)
        run(args.reference, "merge_exp_csv", ratios, items, merged)
        header, features, labels, (size, count, positive) = validated(merged, flags)
        for name, first, rows in (("items.csv", header, features), ("labels.csv", ["#id", "class"], labels)):
            with (args.out / name).open("w", newline="", encoding="ascii") as file:
                writer = csv.writer(file, lineterminator="\n")
                writer.writerow(first)
                writer.writerows(rows)
        summary = dict(genes=size, motifs=count, positives=positive, annotation="GPL570",
                       motif_release="MSigDB C3.TFT 6.0")
        (args.out / "input-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(summary)


if __name__ == "__main__":
    main()
