"""Extract acknowledgements from speech endnotes and save them into a TinyDB.

The original DB (``banca_ditalia_speeches.json``) contains speeches with an
``html_content`` field.  Many speeches include a ``<section role="doc-endnotes">``
whose first ``<li>`` contains an ``<a>`` whose text is exactly ``*`` — this
element holds the author's acknowledgements (people thanked for their help).

This script extracts that acknowledgement text and stores it together with
the original record's metadata (``speaker``, ``location``, ``year``, ``type``,
``link``) in a new TinyDB file (``banca_ditalia_speeches_ack.json``).

Run with::

    uv run python parse_acknowledgements.py
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any

from bs4 import BeautifulSoup
from tinydb import TinyDB

SOURCE_DB = Path("banca_ditalia_speeches.json")
TARGET_DB = Path("banca_ditalia_speeches_ack.json")


def clean_text(text: str) -> str:
    """Normalize whitespace and strip surrounding whitespace."""
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


def extract_acknowledgement(rec: Dict[str, Any]) -> Dict[str, Any] | None:
    """Return a record with the acknowledgement text if one exists, else None."""
    html = rec.get("html_content", "")
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    endnotes = soup.find(attrs={"role": "doc-endnotes"})
    if not endnotes:
        return None

    for li in endnotes.find_all("li"):
        a_tag = li.find("a")
        if a_tag and a_tag.get_text(strip=True) == "*":
            ack_text = clean_text(li.get_text(separator=" "))
            return {
                "acknowledgements": ack_text,
                "speaker": rec.get("speaker"),
                "location": rec.get("location"),
                "year": rec.get("year"),
                "type": rec.get("type"),
                "link": rec.get("link"),
            }
    return None


def main() -> None:
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(f"Source DB not found: {SOURCE_DB}")
    src = TinyDB(str(SOURCE_DB))
    tgt = TinyDB(str(TARGET_DB))

    records = src.all()
    ack_records: List[Dict[str, Any]] = []
    for r in records:
        ack = extract_acknowledgement(r)
        if ack:
            ack_records.append(ack)

    for a in ack_records:
        tgt.insert(a)

    print(f"Processed {len(records)} source entries")
    print(f"Found {len(ack_records)} entries with acknowledgements")
    print(f"New DB written to {TARGET_DB}")


if __name__ == "__main__":
    main()
