"""Split plain text into written-book pages and volumes.

Minecraft wraps book text by pixel width, which we cannot measure exactly
here, so we approximate it with three tunable constants:

* ``LINE_MAX_CHARS``  - characters that fit on one rendered line
* ``PAGE_MAX_LINES``  - rendered lines that fit on one page
* ``PAGE_MAX_CHARS``  - hard cap on characters per page

Text is word-wrapped at ``LINE_MAX_CHARS`` to count lines. Every explicit
line break starts a new line and a blank line (paragraph break) costs one
line. The page string itself keeps the original spacing: wrapped lines of the
same paragraph are joined with a space so the game can re-wrap them itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from .reflow import join_wrapped_lines

PAGE_MAX_CHARS = 230
PAGE_MAX_LINES = 14
LINE_MAX_CHARS = 19

TITLE_MAX_CHARS = 32
BOOK_MAX_PAGES = 100

ELLIPSIS = "…"
DEFAULT_TITLE = "Belge"

# How a rendered line is attached to the previous one in the page string.
_NEWLINE = "\n"  # starts a new source line (or is a blank line)
_SPACE = " "  # word-wrapped continuation of the same paragraph
_NONE = ""  # continuation of a word that was too long for one line


@dataclass(frozen=True)
class _Line:
    text: str
    joiner: str  # one of _NEWLINE, _SPACE, _NONE


@dataclass(frozen=True)
class Volume:
    title: str
    pages: list[str]
    number: int  # 1-based
    total: int


def _check_limits(page_chars: int, page_lines: int, line_chars: int) -> None:
    if min(page_chars, page_lines, line_chars) < 1:
        raise ValueError("page/line limits must be positive")
    if line_chars > page_chars:
        raise ValueError("LINE_MAX_CHARS cannot exceed PAGE_MAX_CHARS")


def _split_long_word(word: str, width: int) -> list[str]:
    return [word[i : i + width] for i in range(0, len(word), width)]


def wrap_lines(text: str, line_chars: int = LINE_MAX_CHARS) -> list[_Line]:
    """Word-wrap ``text`` into rendered lines no longer than ``line_chars``."""
    lines: list[_Line] = []
    for source_line in text.split("\n"):
        words = source_line.split()
        if not words:
            lines.append(_Line("", _NEWLINE))  # blank line still takes a row
            continue

        current = ""
        joiner = _NEWLINE  # joiner for the line being built
        for word in words:
            if current and len(current) + 1 + len(word) <= line_chars:
                current += " " + word
                continue
            if current:
                lines.append(_Line(current, joiner))
                joiner = _SPACE
                current = ""
            if len(word) <= line_chars:
                current = word
                continue
            # Word longer than a whole line (e.g. a URL): hard-split it.
            pieces = _split_long_word(word, line_chars)
            for piece in pieces[:-1]:
                lines.append(_Line(piece, joiner))
                joiner = _NONE
            current = pieces[-1]
        lines.append(_Line(current, joiner))
    return lines


def _render(lines: list[_Line]) -> str:
    out = lines[0].text
    for line in lines[1:]:
        out += line.joiner + line.text
    return out


def paginate(
    text: str,
    page_chars: int = PAGE_MAX_CHARS,
    page_lines: int = PAGE_MAX_LINES,
    line_chars: int = LINE_MAX_CHARS,
) -> list[str]:
    """Split ``text`` into page strings that respect all three limits.

    Blank lines at the start or end of a page are dropped, since they would
    only waste space there.
    """
    _check_limits(page_chars, page_lines, line_chars)

    pages: list[str] = []
    current: list[_Line] = []

    def flush() -> None:
        while current and not current[-1].text:
            current.pop()
        if current:
            pages.append(_render(current))
        current.clear()

    for line in wrap_lines(text, line_chars):
        if not current and not line.text:
            continue  # no blank line at the top of a page
        if current:
            fits_lines = len(current) + 1 <= page_lines
            fits_chars = len(_render(current)) + len(line.joiner) + len(line.text) <= page_chars
            if not (fits_lines and fits_chars):
                flush()
                if not line.text:
                    continue
        current.append(line)
    flush()
    return pages


def truncate_title(title: str, limit: int) -> str:
    title = " ".join(title.split())
    if len(title) <= limit:
        return title
    if limit <= len(ELLIPSIS):
        return title[:limit]
    return title[: limit - len(ELLIPSIS)].rstrip() + ELLIPSIS


def split_volumes(
    title: str,
    pages: list[str],
    max_pages: int = BOOK_MAX_PAGES,
    title_chars: int = TITLE_MAX_CHARS,
) -> list[Volume]:
    """Group ``pages`` into books of at most ``max_pages``.

    A single volume keeps the plain title; several volumes get a
    " (n/N)" suffix and the base title is shortened so the whole title still
    fits in ``title_chars``.
    """
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    base = " ".join(title.split()) or DEFAULT_TITLE
    chunks = [pages[i : i + max_pages] for i in range(0, len(pages), max_pages)]
    total = len(chunks)
    if total == 1:
        return [Volume(truncate_title(base, title_chars), chunks[0], 1, 1)]

    volumes = []
    for number, chunk in enumerate(chunks, start=1):
        suffix = f" ({number}/{total})"
        name = truncate_title(base, title_chars - len(suffix))
        volumes.append(Volume(name + suffix, chunk, number, total))
    return volumes


def make_volumes(title: str, text: str) -> list[Volume]:
    """Re-flow hard-wrapped lines, paginate ``text`` and split it into volumes."""
    pages = paginate(join_wrapped_lines(text))
    if not pages:
        return []
    return split_volumes(title, pages)
