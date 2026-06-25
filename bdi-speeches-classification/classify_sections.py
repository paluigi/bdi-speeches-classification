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

**Resumable:** if the output CSV already exists, the script reads the ``id``
column and skips records that have already been classified.  Each new result
is appended immediately after classification so progress is saved even if the
process is interrupted.

**Short sections:** records with a ``word_count`` < 10 are skipped entirely
(their text is too short for meaningful classification) and are **not**
written to the output file.

Run with::

    uv run python classify_sections.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Set

from ollama import Client
from ollama_classifier import OllamaClassifier
from tinydb import TinyDB

SOURCE_DB = Path("banca_ditalia_speeches_md.json")
CATEGORIES_TSV = Path("categories.tsv")
OUTPUT_CSV = Path("speeches_classified.csv")
MODEL = "qwen3.6:latest"

MIN_WORD_COUNT = 10


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


def already_classified_ids(csv_path: Path) -> Set[int]:
    """Return the set of record IDs that already appear in the output CSV."""
    if not csv_path.is_file():
        return set()
    done: Set[int] = set()
    with open(csv_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                done.add(int(row["id"]))
            except (KeyError, ValueError):
                continue
    return done


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
    # 2. Determine which records need classification
    # ------------------------------------------------------------------
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(f"Source DB not found: {SOURCE_DB}")
    db = TinyDB(str(SOURCE_DB))
    records = db.all()

    done_ids = already_classified_ids(OUTPUT_CSV)

    to_classify = [
        rec for rec in records
        if rec.doc_id not in done_ids and rec.get("word_count", 0) >= MIN_WORD_COUNT
    ]
    skipped_short = [
        rec for rec in records
        if rec.doc_id not in done_ids and rec.get("word_count", 0) < MIN_WORD_COUNT
    ]

    print(f"Total records: {len(records)}")
    print(f"  Already classified: {len(done_ids)}")
    print(f"  Skipped (word_count < {MIN_WORD_COUNT}): {len(skipped_short)}")
    print(f"  To classify now: {len(to_classify)}")

    if not to_classify:
        print("Nothing to do.")
        return

    # ------------------------------------------------------------------
    # 3. Set up classifier
    # ------------------------------------------------------------------
    client = Client()  # default: localhost on standard Ollama port
    classifier = OllamaClassifier(client, model=MODEL)
    print(f"Classifier ready (model: {MODEL})")

    # ------------------------------------------------------------------
    # 4. Classify and write results incrementally
    # ------------------------------------------------------------------
    fieldnames = ["id", *labels, "best_label", "word_count", "title"]
    file_exists = OUTPUT_CSV.is_file()

    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        for i, rec in enumerate(to_classify):
            doc_id = rec.doc_id
            section_title = rec.get("section_title", "")
            section_text = rec.get("section_text", "")
            title = rec.get("title", "")
            word_count = rec.get("word_count", 0)

            # Prepend section_title to give the classifier useful context
            text = f"{section_title}\n\n{section_text}" if section_title else section_text

            result = classifier.classify(text, choices=categories)

            row: dict = {"id": doc_id, "title": title, "word_count": word_count}
            for label in labels:
                row[label] = result.probabilities.get(label, 0.0)
            row["best_label"] = result.prediction
            writer.writerow(row)
            fh.flush()  # persist immediately

            print(
                f"  [{i + 1}/{len(to_classify)}] id={doc_id} {title[:50]:<50} "
                f"→ {result.prediction} ({result.confidence:.2%})"
            )

    print(f"\nDone. Results written to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
