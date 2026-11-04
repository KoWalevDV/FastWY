"""Build a labeled yeast reconstruction from a named GSE18 sample and UCSC sites."""
import argparse
from bisect import bisect_left
from collections import defaultdict
import csv
import gzip
import json
import math
from pathlib import Path
import re
from statistics import median


def tables(path):
    kind = accession = platform = None
    with gzip.open(path, "rt", encoding="latin-1") as stream:
        for line in stream:
            if line.startswith(("^PLATFORM = ", "^SAMPLE = ")):
                entity, accession = line.rstrip().split(" = ", 1)
                kind = entity[1:].lower()
                platform = None
            elif line.startswith("!Sample_platform_id = "):
                platform = line.rstrip().split(" = ", 1)[1]
            elif kind and line.startswith(f"!{kind}_table_begin"):
                header = next(stream).rstrip("\r\n").split("\t")
                def rows():
                    for record in stream:
                        if record.startswith(f"!{kind}_table_end"):
                            break
                        yield record.rstrip("\r\n").split("\t")
                yield kind, accession, platform, header, rows()


def expression(path, sample):
    probes = {}
    for kind, accession, platform, header, rows in tables(path):
        if kind == "platform":
            column = header.index("ORF")
            probes[accession] = {r[0]: r[column] for r in rows
                                 if re.fullmatch(r"Y[A-P][LR]\d{3}[WC](?:-[A-Z])?", r[column])}
        elif accession == sample:
            column = header.index("VALUE")
            values = defaultdict(list)
            for r in rows:
                gene = probes[platform].get(r[0])
                if not gene or not r[column]:
                    continue
                value = float(r[column])
                if math.isfinite(value):
                    values[gene].append(value)
            return {gene: median(masses) for gene, masses in values.items()}
    raise ValueError(f"sample {sample} not found")


def binding_windows(genes_path, sites_path, values):
    by_chromosome = defaultdict(list)
    with gzip.open(sites_path, "rt", encoding="ascii") as sites:
        for row in sites:
            _, chrom, start, end, motif, _, evidence, conserved = row.split()
            if evidence == "good" and int(conserved) >= 2:
                by_chromosome[chrom].append((int(start), int(end), motif))
    for sites in by_chromosome.values():
        sites.sort()
    result = defaultdict(set)
    with gzip.open(genes_path, "rt", encoding="ascii") as genes:
        for row in genes:
            _, gene, chrom, strand, start, end, *_ = row.split("\t")
            if gene not in values:
                continue
            start, end = int(start), int(end)
            lo, hi = (max(0, start - 800), start + 50) if strand == "+" else (end - 50, end + 800)
            sites = by_chromosome[chrom]
            i = bisect_left(sites, (lo,))
            while i < len(sites) and sites[i][0] < hi:
                if sites[i][1] <= hi:
                    result[gene].add(sites[i][2])
                i += 1
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--sample", default="GSM1034")
    args = parser.parse_args()
    values = expression(args.source / "GSE18_family.soft.gz", args.sample)
    genes_path = args.source / "sacCer3_sgdGene.txt.gz"
    with gzip.open(genes_path, "rt", encoding="ascii") as genes:
        ids = sorted({row.split("\t", 2)[1] for row in genes} & values.keys())
    hits = binding_windows(genes_path, args.source / "sacCer3_transRegCode.txt.gz", values)
    motifs = sorted(set().union(*(hits[gene] for gene in ids)))
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "items.csv").open("w", newline="", encoding="ascii") as items, (
        args.output / "labels.csv"
    ).open("w", newline="", encoding="ascii") as labels:
        features = csv.writer(items, lineterminator="\n")
        target = csv.writer(labels, lineterminator="\n")
        features.writerow(["#id", *motifs])
        target.writerow(["#id", "class"])
        for gene in ids:
            features.writerow([gene, *(int(motif in hits[gene]) for motif in motifs)])
            target.writerow([gene, int(values[gene] > 1.0)])
    metadata = {"sample": args.sample, "genes": len(ids), "motifs": len(motifs),
                "positives": sum(values[gene] > 1.0 for gene in ids),
                "genes_with_motifs": sum(bool(hits[gene]) for gene in ids)}
    (args.output / "input-summary.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(metadata)


if __name__ == "__main__":
    main()
