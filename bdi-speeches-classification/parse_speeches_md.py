"""Parse speeches stored in the original TinyDB and produce a Markdown‑friendly
TinyDB.

The original DB (``banca_ditalia_speeches.json``) contains a field
``html_content`` that holds the raw HTML of a speech page.  This script extracts:

1. The speech title (the first ``<h1>``).
2. Each top‑level section delimited by ``<h2>`` tags.
3. Figure information inside a section – ``<figcaption>``, the ``alt`` attribute
   of the ``<img>``, optional ``.fig-notes`` and ``.fig-desc`` elements – and
   injects that information into the section text.
4. Bibliography and end‑notes are ignored (they appear after the last ``<h2>``
   in the original markup).

For every section a new TinyDB record is written with the following fields:

* ``title`` – speech title extracted from ``<h1>``
* ``section_title`` – the ``<h2>`` heading for the section
* ``section_text`` – Markdown formatted text of the section, including figure
  information.
* ``speaker``, ``location``, ``year``, ``type``, ``link`` – copied from the
  source record.
* ``word_count`` – number of words in ``section_text``.

The resulting DB is saved as ``banca_ditalia_speeches_md.json``.

Run with::

    uv run python parse_speeches_md.py

The script is deliberately self‑contained so it works inside the cloned
repository without any additional configuration.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any

from bs4 import BeautifulSoup
from tinydb import TinyDB

SOURCE_DB = Path("banca_ditalia_speeches.json")
TARGET_DB = Path("banca_ditalia_speeches_md.json")


def clean_text(text: str) -> str:
    """Normalize whitespace and strip surrounding newlines."""
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


def extract_figure_md(fig) -> str:
    """Return a Markdown block with information from a ``<figure>`` element.

    The block includes alt text, figcaption, notes (``.fig-notes``) and
    description (``.fig-desc``) if present.
    """
    parts: List[str] = []    
    cap = fig.find("figcaption")
    if cap:
        parts.append(f"**Caption:** {clean_text(cap.get_text(separator=' '))}")
    img = fig.find("img")
    if img and img.get("alt"):
        parts.append(f"**Alt text:** {clean_text(img['alt'])}")
    notes = fig.select_one('.fig-notes')
    if notes:
        parts.append(f"**Notes:** {clean_text(notes.get_text(separator=' '))}")
    desc = fig.select_one('.fig-desc')
    if desc:
        parts.append(f"**Description:** {clean_text(desc.get_text(separator=' '))}")
    if not parts:
        return ""
    return "\n".join(parts) + "\n"


def parse_section(soup_section) -> str:
    """Convert a BeautifulSoup element representing a section into Markdown.

    Handles embedded ``<figure>`` tags by inserting the Markdown produced by
    ``extract_figure_md`` at the point where the figure appears.
    """
    md_chunks: List[str] = []
    for elem in soup_section.contents:
        if isinstance(elem, str):
            md_chunks.append(clean_text(elem))
        else:
            if elem.name == "figure":
                fig_md = extract_figure_md(elem)
                if fig_md:
                    md_chunks.append(fig_md)
            else:
                md_chunks.append(clean_text(elem.get_text(separator=' ')))
    return "\n\n".join(filter(None, md_chunks)).strip()


def process_record(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Transform a raw DB record into one record per speech section.

    Returns a list of new dictionaries ready to be inserted into the target DB.
    """
    html = rec.get("html_content", "")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")

    # Remove end-notes section so its content is not merged into the
    # preceding section during h2 sibling traversal.
    for tag in soup.find_all(attrs={"role": "doc-endnotes"}):
        tag.decompose()

    # Title – first <h1>
    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(separator=' ')) if title_tag else ""

    # Sections – split on <h2>
    sections: List[Dict[str, Any]] = []
    h2_tags = soup.find_all("h2")
    for h2 in h2_tags:
        sec_title = clean_text(h2.get_text(separator=' '))
        # Gather siblings until the next h2
        content_parts = []
        sibling = h2.next_sibling
        while sibling and not (getattr(sibling, "name", None) == "h2"):
            fragment = BeautifulSoup(str(sibling), "html.parser")
            content_parts.append(fragment)
            sibling = sibling.next_sibling
        combined = BeautifulSoup("", "html.parser")
        for part in content_parts:
            combined.append(part)
        section_md = parse_section(combined)
        word_cnt = len(section_md.split()) if section_md else 0
        sections.append({
            "title": title,
            "section_title": sec_title,
            "section_text": section_md,
            "speaker": rec.get("speaker"),
            "location": rec.get("location"),
            "year": rec.get("year"),
            "type": rec.get("type"),
            "link": rec.get("link"),
            "word_count": word_cnt,
        })
    return sections


def main() -> None:
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(f"Source DB not found: {SOURCE_DB}")
    src = TinyDB(str(SOURCE_DB))
    tgt = TinyDB(str(TARGET_DB))
    records = src.all()
    new_records: List[Dict[str, Any]] = []
    for r in records:
        new_records.extend(process_record(r))
    for nr in new_records:
        tgt.insert(nr)
    print(f"Converted {len(records)} source entries into {len(new_records)} section entries")
    print(f"New DB written to {TARGET_DB}")


if __name__ == "__main__":
    main()
