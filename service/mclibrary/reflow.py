"""Undo hard line wrapping inside paragraphs.

Text copied or extracted from PDFs has a line break at the end of every
visual line ("...hizmetlerin\\nülke düzeyinde..."). In a book those breaks
would cut sentences in half and waste lines, so before paginating we join a
line with the next one when it clearly continues the same sentence:

* the line does not end with sentence punctuation (. ! ? : …), and
* the next line starts with a lowercase letter, and
* the next line is not a list item ("-", "•", "*", "1.", "2)" ...).

A line ending in a hyphenated word ("yapılan-") followed by a lowercase line
is joined without the hyphen ("yapılanması").

Blank lines (paragraph breaks) are kept as they are.

A line ending in ``HARD_BREAK`` is never joined with the next one. Markdown
extraction puts this marker where the source had a hard line break (two
trailing spaces or a trailing backslash); ``join_wrapped_lines`` removes every
marker from its output.

Case is tested with ``str.islower()``, which is Unicode-aware and classifies
the Turkish letters correctly: "ı", "i", "ş", "ğ" are lowercase; "I", "İ",
"Ş", "Ğ" are not. We never call ``lower()``/``upper()``, whose locale-free
mappings (İ -> "i̇", i -> "I") are wrong for Turkish.
"""

from __future__ import annotations

import re

SENTENCE_END = (".", "!", "?", ":", "…")

# Private-use character: never occurs in real text and is not rendered.
HARD_BREAK = ""

_LIST_ITEM_RE = re.compile(r"^\s*(?:[-•*–—]\s|\d{1,3}[.)]\s)")
_HYPHENATED_END_RE = re.compile(r"[^\W\d_]-$")  # a letter followed by "-"


def is_list_item(line: str) -> bool:
    return bool(_LIST_ITEM_RE.match(line))


def starts_lowercase(line: str) -> bool:
    stripped = line.lstrip()
    return bool(stripped) and stripped[0].islower()


def _join_paragraph(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not out:
            out.append(line.rstrip())
            continue
        prev = out[-1]
        nxt = line.strip()
        if prev.endswith(HARD_BREAK) or is_list_item(line) or not starts_lowercase(nxt):
            out.append(line.rstrip())
        elif _HYPHENATED_END_RE.search(prev):
            out[-1] = prev[:-1] + nxt
        elif not prev.endswith(SENTENCE_END):
            out[-1] = prev + " " + nxt
        else:
            out.append(line.rstrip())
    return out


def join_wrapped_lines(text: str) -> str:
    """Join hard-wrapped lines within each paragraph of ``text``."""
    result: list[str] = []
    paragraph: list[str] = []
    for line in text.split("\n"):
        if line.strip():
            paragraph.append(line)
            continue
        result.extend(_join_paragraph(paragraph))
        paragraph = []
        result.append("")
    result.extend(_join_paragraph(paragraph))
    return "\n".join(line.replace(HARD_BREAK, "").rstrip() for line in result)
