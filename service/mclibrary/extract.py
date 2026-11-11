"""Extract plain text from .txt, .md and .pdf files.

Files that cannot be turned into text (scanned PDFs, corrupt files, unknown
encodings, ...) are never fatal: they are reported as ``SkippedFile`` entries
with a human-readable reason so the caller can tell the player what happened.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

log = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}

# Tried in order. utf-8-sig also strips a BOM if present; cp1254 is the
# Windows Turkish code page that Notepad and older tools often produce.
TEXT_ENCODINGS = ("utf-8-sig", "cp1254")


class ExtractionError(Exception):
    """Raised when a file cannot be turned into usable text."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Document:
    path: Path  # relative to the library directory
    text: str


@dataclass(frozen=True)
class SkippedFile:
    path: Path  # relative to the library directory
    reason: str


UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")  # little-endian, big-endian


def read_text_file(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(UTF16_BOMS):
        # Notepad's "Unicode" option. The "utf-16" codec reads the BOM to pick
        # the byte order and drops it from the result.
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise ExtractionError("UTF-16 dosyası bozuk") from exc
    for encoding in TEXT_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("metin kodlaması tanınamadı (UTF-8 veya Windows-1254 değil)")


_MD_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^```.*$", re.MULTILINE), ""),  # code fence lines, keep the code
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),  # images -> alt text
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),  # links -> link text
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE), ""),  # heading markers
    (re.compile(r"^\s{0,3}>\s?", re.MULTILINE), ""),  # blockquotes
    (re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$", re.MULTILINE), ""),  # horizontal rules
    (re.compile(r"^(\s*)[*+]\s+", re.MULTILINE), r"\1- "),  # bullets -> "- "
    (re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1"), r"\2"),  # bold
    (re.compile(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])"), r"\1"),  # *italic*
    (re.compile(r"(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)"), r"\1"),  # _italic_ (not snake_case)
    (re.compile(r"~~(.+?)~~"), r"\1"),  # strikethrough
    (re.compile(r"`([^`]+)`"), r"\1"),  # inline code
    (re.compile(r"<[^>\n]+>"), ""),  # inline HTML tags
]


def simplify_markdown(text: str) -> str:
    for pattern, repl in _MD_RULES:
        text = pattern.sub(repl, text)
    return text


# A PDF whose pages carry fewer letters than this on average (after removing
# printer marks) is treated as image-only / outlined-text.
MIN_LETTERS_PER_PAGE = 50

# Printer's slug line, e.g. "PSIKOLOJI KAPAK.fh11 3/2/11 3:28 PM Page 1".
# The file name may contain spaces, so everything from the line start up to
# the layout-program extension is consumed.
_SLUG_RE = re.compile(
    r"^[^\n]*?\.(?:fh\d*|indd|ai|qxd|qxp|p65|pm\d*|cdr|eps)\s+"
    r"\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\s+"
    r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AP]M)?\s+"
    r"Page\s+\d+[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)
# "Composite" and colour-separation lines such as "C M Y CM MY CY CMY K".
_SEPARATION_TOKEN = r"(?:Composite|C|M|Y|K|CM|MY|CY|CMY|CMYK|Cyan|Magenta|Yellow|Black)"
_SEPARATION_LINE_RE = re.compile(
    rf"^[ \t]*(?:Composite|{_SEPARATION_TOKEN}(?:[ \t]+{_SEPARATION_TOKEN})+)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_print_marks(text: str) -> str:
    """Remove prepress imprint lines that layout programs stamp on each page."""
    text = _SLUG_RE.sub("", text)
    text = _SEPARATION_LINE_RE.sub("", text)
    return text


def count_letters(text: str) -> int:
    return sum(1 for ch in text if ch.isalpha())


def read_pdf(path: Path) -> str:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            # Many PDFs are "encrypted" with an empty user password.
            try:
                if not reader.decrypt(""):
                    raise ExtractionError("PDF şifreli")
            except ExtractionError:
                raise
            except Exception as exc:
                raise ExtractionError("PDF şifreli") from exc
        pages = [page.extract_text() or "" for page in reader.pages]
    except ExtractionError:
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        raise ExtractionError(f"PDF okunamadı ({exc.__class__.__name__})") from exc
    except Exception as exc:  # pypdf can raise many things on broken files
        log.exception("Unexpected error while reading %s", path)
        raise ExtractionError(f"PDF okunamadı ({exc.__class__.__name__})") from exc

    pages = [strip_print_marks(p).strip() for p in pages]
    text = "\n\n".join(p for p in pages if p)
    page_count = max(len(pages), 1)
    if count_letters(text) / page_count < MIN_LETTERS_PER_PAGE:
        raise ExtractionError("PDF'te metin yok (görsel/çizime dönüştürülmüş PDF olabilir)")
    return text


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    text = "".join(ch for ch in text if ch == "\n" or ch.isprintable())
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(path: Path) -> str:
    """Return the normalized text of ``path`` or raise ``ExtractionError``."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        raw = read_pdf(path)
    elif suffix in (".txt", ".md"):
        try:
            raw = read_text_file(path)
        except OSError as exc:
            raise ExtractionError(f"dosya okunamadı ({exc.__class__.__name__})") from exc
        if suffix == ".md":
            raw = simplify_markdown(raw)
    else:
        raise ExtractionError(f"desteklenmeyen dosya türü: {suffix or '(uzantısız)'}")

    text = normalize(raw)
    if not text:
        raise ExtractionError("dosya boş")
    return text


def scan_library(library_dir: Path) -> tuple[list[Document], list[SkippedFile]]:
    """Read every supported file under ``library_dir`` (recursively).

    Hidden files/folders (starting with ".") and unsupported extensions are
    ignored silently. Returned lists are sorted by path for stable output.
    """
    if not library_dir.is_dir():
        raise FileNotFoundError(f"LIBRARY_DIR is not a directory: {library_dir}")

    documents: list[Document] = []
    skipped: list[SkippedFile] = []
    for path in sorted(library_dir.rglob("*")):
        rel = path.relative_to(library_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            documents.append(Document(rel, extract_text(path)))
        except ExtractionError as exc:
            log.warning("Skipping %s: %s", rel, exc.reason)
            skipped.append(SkippedFile(rel, exc.reason))
    return documents, skipped
