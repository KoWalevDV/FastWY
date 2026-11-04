import csv
from decimal import Decimal, localcontext
from pathlib import Path
import math
import re
import sys

sys.path.insert(0, "scripts")
from compare_runs import read_run

out = Path("experiments/10-mushroom-author-direct")
_, author = read_run(out / "author.tsv", True)
threshold, cpp = read_run(out / "cpp.tsv", False)
diff = sorted(cpp.keys() - author.keys())
logs = {}
for name, folder in (("original", "mushroom-direct"), ("accelerated", "replay-05-mushroom-lcm")):
    content = (Path("build") / folder / "author.log").read_text()
    logs[name] = dict(re.findall(r"^\[permute (\d+)\] minP ([^,]+)", content, re.M))
rank50 = sorted(map(Decimal, logs["original"].values()))[49]
with (out / "minima-differences.tsv").open("w", newline="") as target:
    writer = csv.writer(target, delimiter="\t", lineterminator="\n")
    writer.writerow(("permutation_zero_based", "original_min_p", "accelerated_min_p"))
    for index, value in logs["original"].items():
        fast = logs["accelerated"][index]
        if not math.isclose(float(value), float(fast), rel_tol=1e-8):
            writer.writerow((index, value, fast))
print("author rank 50", rank50, "cpp", threshold)
sys.path.insert(0, str(Path("build/reference/lamp-master").resolve()))
import readFile
from functions.functions4fisher import FunctionOfX

base = "experiments/05-mushroom-lcm"
transactions, names = readFile.readFiles(base + "/items.csv", base + "/labels.csv", ",")
# The author cache is dimensioned by the maximum singleton support.
max_support = max(sum(i in t.itemset for t in transactions) for i in range(1, len(names) + 1))
test = FunctionOfX(transactions, max_support, 1)
n = len(transactions)
positive = sum(int(t.value) for t in transactions)
with (out / "cpp-only.tsv").open("w", newline="") as target:
    writer = csv.writer(target, delimiter="\t", lineterminator="\n")
    writer.writerow(("pattern", "support", "positive", "p_exact", "author_fisher", "author_rank50"))
    for key in diff:
        support, positives, _, _ = cpp[key]
        ids = {names.index(name) + 1 for name in key}
        cover = [t.getID() for t in transactions if ids <= t.itemset]
        reference_p, reference_positives = test.calPValue(transactions, cover)
        assert len(cover) == support and reference_positives == positives
        mass = sum(math.comb(positive, k) * math.comb(n - positive, support - k)
                   for k in range(positives, min(support, positive) + 1))
        with localcontext() as ctx:
            ctx.prec = 32
            exact = Decimal(mass) / math.comb(n, support)
        writer.writerow((",".join(key), support, positives, exact, reference_p, rank50))
print("maximum support", max_support)
print("count discrepancies", sum(author[k][:2] != cpp[k][:2] for k in author))
print("all positive counts match", all(author[k][1] == cpp[k][1] for k in author))
