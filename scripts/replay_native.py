"""Run the author support traversal with packed disk records and native label counts."""
import argparse
import ctypes as ct
from ctypes import wintypes as wt
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryFile
import time

import replay_reference as replay


class PackedBucket(replay.DiskBucket):
    def append(self, record):
        if self.file is None:
            self.file = TemporaryFile(dir=self.directory)
        if self.reading:
            self.file.seek(0, 2)
            self.reading = False
        items, rows = record
        values = tuple(items) + tuple(rows)
        payload = struct.pack(f"<{len(values)}I", *values)
        self.file.write(struct.pack("<II", len(items), len(rows)))
        self.file.write(payload)
        self.size += 1

    def __iter__(self):
        if self.file is None:
            return
        self.file.seek(0)
        self.reading = True
        for _ in range(self.size):
            items, rows = struct.unpack("<II", self.file.read(8))
            values = struct.unpack(f"<{items + rows}I", self.file.read(4 * (items + rows)))
            yield set(values[:items]), list(values[items:])


def install_native(fastwy, library):
    import msvcrt
    callback_type = ct.CFUNCTYPE(ct.c_double, ct.POINTER(ct.c_uint32), ct.c_uint32, ct.c_uint32)
    library.scan.argtypes = [ct.c_size_t, ct.POINTER(ct.c_ubyte), ct.c_uint32,
                             ct.c_uint64, callback_type, ct.POINTER(ct.c_double)]
    library.scan.restype = ct.c_int
    library.clear_cache.argtypes = []
    library.clear_cache.restype = None

    def minimum(transactions, filename, miner, statistic, max_comb, mapping):
        size = len(transactions)
        labels = (ct.c_ubyte * size)(*(int(transactions[mapping[row]].value) for row in range(size)))
        failure = []

        @callback_type
        def probability(rows, support, positive):
            try:
                ids = [mapping[rows[index]] for index in range(support)]
                value, observed = statistic.calPValue(transactions, ids)
                if observed != positive:
                    raise ValueError("native label count differs from the author")
                return value
            except BaseException as error:
                failure.append(error)
                return float("nan")

        current = ct.c_double(1.0)
        support = miner.max_support
        mining_time = 0.0
        while True:
            start = time.time()
            miner.frequentPatterns(filename, support, max_comb)
            bound = miner.getBound(support)
            if bound > 1:
                bound = statistic.funcF(support)
                miner.setBound(support, bound)
            bucket = miner.getFrequentList(support)
            mining_time += time.time() - start
            if len(bucket):
                bucket.file.flush()
                handle = msvcrt.get_osfhandle(bucket.file.fileno())
                code = library.scan(handle, labels, size, len(bucket), probability, ct.byref(current))
                if failure:
                    raise failure[0]
                if code:
                    raise RuntimeError(f"native disk scan failed with code {code}")
            if current.value < bound or support <= 1:
                return current.value, support, mining_time
            support -= 1

    fastwy.calculateMinimumPValue = minimum


class ProcessMemory(ct.Structure):
    _fields_ = [("cb", wt.DWORD), ("faults", wt.DWORD),
                ("peak_working_set", ct.c_size_t), ("working_set", ct.c_size_t),
                ("peak_paged", ct.c_size_t), ("paged", ct.c_size_t),
                ("peak_nonpaged", ct.c_size_t), ("nonpaged", ct.c_size_t),
                ("commit", ct.c_size_t), ("peak_commit", ct.c_size_t)]


def memory_diagnostic():
    kernel = ct.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wt.HANDLE
    query = kernel.K32GetProcessMemoryInfo
    query.argtypes = [wt.HANDLE, ct.POINTER(ProcessMemory), wt.DWORD]
    query.restype = wt.BOOL
    counters = ProcessMemory()
    counters.cb = ct.sizeof(counters)
    if query(kernel.GetCurrentProcess(), ct.byref(counters), counters.cb):
        print("native_memory=" + json.dumps({
            "peak_root_working_set_bytes": counters.peak_working_set,
            "peak_root_commit_bytes": counters.peak_commit,
        }), file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Remaining arguments follow replay_reference.py; --disk-cache is required.")
    parser.add_argument("--scanner", required=True, type=Path)
    options, arguments = parser.parse_known_args()
    library = ct.CDLL(str(options.scanner.resolve()))

    def setup(args, fastwy):
        if not args.disk_cache or args.accelerate:
            parser.error("--disk-cache is required and --accelerate is incompatible")
        replay.DiskBucket = PackedBucket
        install_native(fastwy, library)

    sys.argv = [sys.argv[0], *arguments]
    try:
        replay.main(setup=setup)
    finally:
        memory_diagnostic()
        library.clear_cache()


if __name__ == "__main__":
    main()
