"""Inventory heat-shock samples and expression coverage from the GEO SOFT file."""
import csv
import gzip
from pathlib import Path
import re
import sys


def parse(source, annotated):
    platforms = {}
    sample = platform = title = None
    with gzip.open(source, "rt", encoding="latin-1") as stream:
        for line in stream:
            if line.startswith("^PLATFORM = "):
                platform = line.strip().split()[-1]
            elif line.startswith("!platform_table_begin"):
                header = next(stream).rstrip("\r\n").split("\t")
                index = header.index("ORF")
                mapping = {}
                for row in stream:
                    if row.startswith("!platform_table_end"):
                        break
                    fields = row.rstrip("\r\n").split("\t")
                    if index < len(fields):
                        orf = fields[index].upper()
                        if re.fullmatch(r"Y[A-P][LR]\d{3}[WC](?:-[A-Z])?", orf):
                            mapping[fields[0]] = orf
                platforms[platform] = mapping
            elif line.startswith("^SAMPLE = "):
                sample = line.strip().split()[-1]
                platform = title = None
            elif line.startswith("!Sample_platform_id = "):
                platform = line.strip().split()[-1]
            elif line.startswith("!Sample_title = "):
                title = line.strip().partition(" = ")[2]
            elif line.startswith("!sample_table_begin") and title and re.search(
                r"heat.shock|25.*37|37.*25", title, re.I
            ):
                column = next(stream).rstrip("\r\n").split("\t").index("VALUE")
                mapping = platforms[platform]
                genes = set()
                valid = 0
                for row in stream:
                    if row.startswith("!sample_table_end"):
                        break
                    fields = row.rstrip("\r\n").split("\t")
                    try:
                        float(fields[column])
                    except ValueError:
                        continue
                    valid += 1
                    if fields[0] in mapping:
                        genes.add(mapping[fields[0]])
                yield sample, title, platform, valid, len(genes), len(genes & annotated)


if __name__ == "__main__":
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    with gzip.open(sys.argv[2], "rt", encoding="ascii") as genes:
        annotated = {row.split("\t", 2)[1] for row in genes}
    writer.writerow(("sample", "title", "platform", "nonempty_value", "distinct_orfs", "in_sgd"))
    writer.writerows(parse(Path(sys.argv[1]), annotated))
