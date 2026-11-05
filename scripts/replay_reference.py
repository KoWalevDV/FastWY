"""Run author FastWY on a fixed permutation file, with optional Fisher acceleration."""
import argparse
import csv
import math
import pickle
import struct
from tempfile import TemporaryFile
import sys
import time
from pathlib import Path

from verify_lcm import make_fisher, pack


def accelerate(fastwy, size, positive):
    """Preserve author support traversal and cutoff; cache equivalent statistics."""
    fisher = make_fisher(size, positive)
    coverages = {}
    source = None

    def minimum(transactions, filename, miner, stat, max_comb, mapping):
        nonlocal source
        if source is not miner:
            source = miner
            coverages.clear()
        labels = pack((i for i, at in enumerate(mapping) if transactions[at].value), size)
        current = 0.0
        support = miner.max_support
        mining_time = 0.0
        while True:
            start = time.perf_counter()
            miner.frequentPatterns(filename, support, max_comb)
            if support not in coverages:
                coverages[support] = [(pack(rows, size), len(rows))
                                      for _, rows in miner.getFrequentList(support)]
            mining_time += time.perf_counter() - start
            bound = fisher(support)[1][-1]
            for coverage, actual in coverages[support]:
                lo, tail = fisher(actual)
                if current > tail[-1]:
                    current = min(current, tail[(labels & coverage).bit_count() - lo])
            if current < bound or support <= 1:
                return math.exp(current), support, mining_time
            support -= 1

    def original_labels(transactions, filename, miner, stat, max_comb, threshold, log):
        labels = pack((t.getID() for t in transactions if t.value), size)
        target = math.log(threshold) if threshold else -math.inf
        start = time.perf_counter()
        mining_time = 0.0
        support = miner.max_support
        results = []
        while True:
            tick = time.perf_counter()
            miner.frequentPatterns(filename, support, max_comb)
            entries = miner.getFrequentList(support)
            if support not in coverages:
                coverages[support] = [(pack(rows, size), len(rows)) for _, rows in entries]
            mining_time += time.perf_counter() - tick
            for (items, _), (coverage, actual) in zip(entries, coverages[support]):
                lo, tail = fisher(actual)
                a = (labels & coverage).bit_count()
                p = tail[a - lo]
                if p <= target + 2e-10:
                    results.append([items, math.exp(p), actual, a])
            if target + 2e-10 < fisher(support)[1][-1] or support <= 1:
                return results, mining_time, time.perf_counter() - start
            support -= 1

    fastwy.calculateMinimumPValue = minimum
    fastwy.enumerateSigComb = original_labels


class DiskBucket:
    """Append-only sequence, replayed in the original order from a temporary file."""

    def __init__(self, directory):
        self.directory = directory
        self.file = None
        self.size = 0
        self.reading = False

    def append(self, record):
        if self.file is None:
            self.file = TemporaryFile(dir=self.directory)
        if self.reading:
            self.file.seek(0, 2)
            self.reading = False
        payload = pickle.dumps(record, protocol=pickle.HIGHEST_PROTOCOL)
        self.file.write(struct.pack("<I", len(payload)))
        self.file.write(payload)
        self.size += 1

    def __len__(self):
        return self.size

    def __getitem__(self, index):
        if index < 0:
            index += self.size
        for position, record in enumerate(self):
            if position == index:
                return record
        raise IndexError(index)

    def __iter__(self):
        if self.file is None:
            return
        self.file.seek(0)
        self.reading = True
        for _ in range(self.size):
            length = struct.unpack("<I", self.file.read(4))[0]
            yield pickle.loads(self.file.read(length))


def use_disk_buckets(directory):
    from frepattern.nodeClass import Node

    directory.mkdir(parents=True, exist_ok=True)
    initialize = Node.__init__

    def initialize_with_disk(self):
        initialize(self)
        self.itemset_list = DiskBucket(directory)

    Node.__init__ = initialize_with_disk



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("permutations", type=Path)
    parser.add_argument("log", type=Path)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--accelerate", action="store_true")
    parser.add_argument("--disk-cache", type=Path)
    args = parser.parse_args()
    if args.disk_cache and args.accelerate:
        parser.error("--disk-cache cannot be combined with --accelerate")
    sys.path.insert(0, str(args.reference.resolve()))
    import fastwy
    if args.disk_cache:
        use_disk_buckets(args.disk_cache)

    with (args.inputs / "labels.csv").open(newline="", encoding="ascii") as file:
        records = list(csv.reader(file))[1:]
    by_name = {row[0]: i for i, row in enumerate(records)}
    positive = sum(int(row[1]) for row in records)
    if args.accelerate:
        accelerate(fastwy, len(records), positive)

    with args.permutations.open(newline="", encoding="ascii") as file:
        rows = csv.reader(file)

        def replay(transactions, values):
            row = next(rows)
            if len(row) != len(records) or set(row) - {"0", "1"} or row.count("1") != positive:
                raise ValueError("invalid fixed permutation")
            result = []
            mapping = [0] * len(transactions)
            for transaction in transactions:
                mapping[transaction.getID()] = len(result)
                copy = transaction.copy()
                copy.setValue(int(row[by_name[transaction.name]]))
                result.append(copy)
            return result, mapping

        fastwy.permuteData = replay
        fastwy.run((args.inputs / "items.csv").as_posix(),
                   (args.inputs / "labels.csv").as_posix(), 0.05, args.count, "fisher",
                   args.reference.as_posix() + "/lcm53/lcm.exe", "all", str(args.log), 1)


if __name__ == "__main__":
    main()
