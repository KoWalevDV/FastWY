"""Convert the original UCI rows to deterministic binary FastWY input."""
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "uci"
MUSHROOM = (
    "cap-shape cap-surface cap-color bruises odor gill-attachment gill-spacing "
    "gill-size gill-color stalk-shape stalk-root stalk-surface-above-ring "
    "stalk-surface-below-ring stalk-color-above-ring stalk-color-below-ring "
    "veil-type veil-color ring-number ring-type spore-print-color population habitat"
).split()
BOARD = [f"{row}-{column}" for row in ("top", "middle", "bottom")
         for column in ("left", "middle", "right")]


def convert(name, filename, attributes, count, classes, class_first):
    path = ROOT / "raw" / filename
    with path.open(newline="", encoding="ascii") as source:
        rows = list(csv.reader(source))
    if len(rows) != count or any(len(row) != len(attributes) + 1 for row in rows):
        raise ValueError(f"{filename}: unexpected dataset dimensions")

    observations = [row[1:] if class_first else row[:-1] for row in rows]
    labels = [row[0] if class_first else row[-1] for row in rows]
    if set(labels) != set(classes):
        raise ValueError(f"{filename}: unexpected class labels")

    # Preserve missing categories as explicit indicators and keep source order.
    indicators = [(index, value) for index, values in enumerate(zip(*observations))
                  for value in sorted(set(values))]
    names = [f"{attributes[index]}={value}" for index, value in indicators]
    out = ROOT / name
    out.mkdir(exist_ok=True)
    with (out / "items.csv").open("w", newline="", encoding="ascii") as features, (
        out / "labels.csv"
    ).open("w", newline="", encoding="ascii") as target:
        items = csv.writer(features, lineterminator="\n")
        outcomes = csv.writer(target, lineterminator="\n")
        items.writerow(["#id", *names])
        outcomes.writerow(["#id", "class"])
        for i, (values, label) in enumerate(zip(observations, labels), 1):
            row_id = f"row-{i:05d}"
            items.writerow([row_id, *(int(values[j] == value) for j, value in indicators)])
            outcomes.writerow([row_id, classes[label]])
    print(f"{name}: {count} rows, {len(names)} indicators, "
          f"{sum(classes[label] for label in labels)} positive; "
          f"source SHA-256 {hashlib.sha256(path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    convert("mushroom", "agaricus-lepiota.data", MUSHROOM, 8124, {"e": 0, "p": 1}, True)
    convert("tic-tac-toe", "tic-tac-toe.data", BOARD, 958, {"negative": 0, "positive": 1}, False)
