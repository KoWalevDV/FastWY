"""Regression tests for the disk-backed author sequence."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from replay_reference import DiskBucket


class StorageTest(unittest.TestCase):
    def test_replay_and_append(self):
        with tempfile.TemporaryDirectory() as directory:
            bucket = DiskBucket(directory)
            self.assertEqual(list(bucket), [])
            records = [({1, 2}, [0, 4]), ({3}, [1, 3, 5])]
            for record in records:
                bucket.append(record)
            self.assertEqual(list(bucket), records)
            self.assertEqual(list(bucket), records)
            self.assertEqual(bucket[0], records[0])
            self.assertEqual(bucket[-1], records[-1])
            with self.assertRaises(IndexError):
                _ = bucket[2]
            partial = iter(bucket)
            self.assertEqual(next(partial), records[0])
            partial.close()
            last = ({4}, [2])
            bucket.append(last)
            self.assertEqual(list(bucket), records + [last])
            bucket.file.close()


if __name__ == "__main__":
    unittest.main()
