"""Classify all speech sections from the Markdown TinyDB using ollama-classifier.

Reads ``banca_ditalia_speeches_md.json``, loads category labels and descriptions
from ``categories.tsv``, and uses :class:`ollama_classifier.OllamaClassifier`
with the ``classify`` method (multi-call evaluation) to obtain a probability
distribution over categories for every section.

The results are written to ``speeches_classified.csv`` with one row per section
and the following columns:

* ``id`` – the element ID from the source TinyDB.
* One column per category label – containing the probability for that label.
* ``best_label`` – the label with the highest probability.
* ``word_count`` – word count of the section (from the source record).
* ``title`` – speech title (from the source record).

Run with::

    uv run python classify_sections.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from ollama import Client
from ollama_classifier import OllamaClassifier
from tinydb import TinyDB

SOURCE_DB = Path("banca_ditalia_speeches_md.json")
CATEGORIES_TSV = Path("categories.tsv")
OUTPUT_CSV = Path("speeches_classified.csv")
MODEL = "gemma4:31b-it-q8_0"


def load_categories(tsv_path: Path) -> Dict[str, str]:
    """Load categories from a TSV file.

    Returns a dict mapping *label* → *description* using the first two columns.
    """
    categories: Dict[str, str] = {}
    with open(tsv_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            label = row["label"]
            description = row["description"]
            categories[label] = description
    return categories


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Load categories
    # ------------------------------------------------------------------
    if not CATEGORIES_TSV.is_file():
        raise FileNotFoundError(f"Categories file not found: {CATEGORIES_TSV}")
    categories = load_categories(CATEGORIES_TSV)
    labels = list(categories.keys())
    print(f"Loaded {len(labels)} categories")

    # ------------------------------------------------------------------
    # 2. Set up classifier
    # ------------------------------------------------------------------
    client = Client()  # default: localhost on standard Ollama port
    classifier = OllamaClassifier(client, model=MODEL)
    print(f"Classifier ready (model: {MODEL})")

    # ------------------------------------------------------------------
    # 3. Load source records
    # ------------------------------------------------------------------
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(f"Source DB not found: {SOURCE_DB}")
    db = TinyDB(str(SOURCE_DB))
    records = db.all()
    print(f"Loaded {len(records)} section records from {SOURCE_DB}")

    # ------------------------------------------------------------------
    # 4. Classify each section and build rows
    # ------------------------------------------------------------------
    rows: List[dict] = []
    for rec in records:
        doc_id = rec.doc_id
        text = rec.get("section_text", "")
        title = rec.get("title", "")
        word_count = rec.get("word_count", 0)

        result = classifier.classify(text, choices=categories)

        row: dict = {"id": doc_id, "title": title, "word_count": word_count}
        for label in labels:
            row[label] = result.probabilities.get(label, 0.0)
        row["best_label"] = result.prediction
        rows.append(row)

        print(
            f"  [{doc_id}] {title[:50]:<50} → {result.prediction} "
            f"({result.confidence:.2%})"
        )

    # ------------------------------------------------------------------
    # 5. Write CSV
    # ------------------------------------------------------------------
    fieldnames = ["id", *labels, "best_label", "word_count", "title"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {len(rows)} rows written to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
