from pathlib import Path

import pytest
from pypdf import PdfWriter

from mclibrary.extract import (
    ExtractionError,
    extract_text,
    scan_library,
    simplify_markdown,
    strip_print_marks,
)

TURKISH = "Şişli'de ılık bir gün. İğde ağacı, Çağrı ve Öykü; ĞÜŞİÖÇ ğüşıöç."


LOREM = (
    "Kutuphanenin raflarinda binlerce kitap duruyordu ve her biri "
    "okunmayi bekliyordu."
)

# Text pypdf extracted from a real brochure whose body text was outlined.
BROCHURE_IMPRINT = [
    "PSIKOLOJI KAPAK.fh11 3/2/11 3:28 PM Page 1",
    "Composite",
    "C M Y CM MY CY CMY K",
    "psikostrayfalarCON.fh11 2/26/11 4:48 PM Page 4",
    "Composite",
    "C M Y CM MY CY CMY K",
]


def make_text_pdf(path: Path, text: str | list[str]) -> None:
    """Write a minimal one-page PDF that draws each line of ``text``."""
    lines = [text] if isinstance(text, str) else text
    shows = " ".join(f"({line}) Tj 0 -14 Td" for line in lines)
    content = f"BT /F1 12 Tf 72 720 Td {shows} ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    path.write_bytes(bytes(out))


def make_blank_pdf(path: Path, password: str | None = None) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    if password:
        writer.encrypt(password)
    with path.open("wb") as fh:
        writer.write(fh)


# --- Turkish characters / encodings -------------------------------------------------


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1254"])
def test_turkish_text_survives_every_encoding(tmp_path, encoding):
    f = tmp_path / "turkce.txt"
    f.write_bytes(TURKISH.encode(encoding))
    assert extract_text(f) == TURKISH


@pytest.mark.parametrize(
    "bom, encoding",
    [(b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")],
    ids=["FF FE (LE)", "FE FF (BE)"],
)
def test_utf16_with_bom(tmp_path, bom, encoding):
    f = tmp_path / "unicode.txt"
    f.write_bytes(bom + f"{TURKISH}\r\nikinci satır".encode(encoding))
    assert extract_text(f) == f"{TURKISH}\nikinci satır"  # no BOM, CRLF normalized


def test_utf16_markdown(tmp_path):
    f = tmp_path / "notlar.md"
    f.write_bytes(f"# Başlık\n\n{TURKISH}".encode("utf-16"))  # Python writes a BOM
    assert extract_text(f) == f"Başlık\n\n{TURKISH}"


def test_corrupt_utf16_is_reported(tmp_path):
    f = tmp_path / "bozuk.txt"
    f.write_bytes(b"\xff\xfe" + "a".encode("utf-16-le") + b"\x00\xd8")  # lone surrogate
    with pytest.raises(ExtractionError, match="UTF-16"):
        extract_text(f)


def test_turkish_markdown_cp1254(tmp_path):
    f = tmp_path / "notlar.md"
    f.write_bytes(f"# Başlık\n\n**{TURKISH}**".encode("cp1254"))
    assert extract_text(f) == f"Başlık\n\n{TURKISH}"


def test_utf8_is_preferred_over_cp1254(tmp_path):
    # "ş" in UTF-8 is two bytes that are *also* valid cp1254 ("ÅŸ");
    # UTF-8 must win so we don't produce mojibake.
    f = tmp_path / "a.txt"
    f.write_bytes("ş".encode("utf-8"))
    assert extract_text(f) == "ş"


# --- text / markdown -----------------------------------------------------------------


def test_normalizes_line_endings_and_blank_lines(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"satir1\r\n\r\n\r\n\r\nsatir2   \r\n")
    assert extract_text(f) == "satir1\n\nsatir2"


def test_empty_file_raises(tmp_path):
    f = tmp_path / "bos.txt"
    f.write_bytes(b"  \n\n ")
    with pytest.raises(ExtractionError, match="boş"):
        extract_text(f)


def test_markdown_is_simplified():
    md = (
        "## Bölüm 1\n"
        "Bir [bağlantı](http://x.y) ve ![resim](a.png) ile **kalın**, *eğik*, `kod`.\n"
        "> alıntı\n"
        "* madde\n"
        "---\n"
        "değişken_adı korunur\n"
        "```python\nprint(1)\n```"
    )
    out = simplify_markdown(md)
    assert "Bölüm 1" in out and "#" not in out
    assert "bir bağlantı ve resim ile kalın, eğik, kod." in out.lower()
    assert "alıntı" in out and ">" not in out
    assert "- madde" in out
    assert "---" not in out
    assert "değişken_adı korunur" in out
    assert "print(1)" in out and "```" not in out


# --- PDF -----------------------------------------------------------------------------


def test_pdf_with_text(tmp_path):
    f = tmp_path / "metin.pdf"
    make_text_pdf(f, LOREM)
    assert LOREM in extract_text(f)


def test_pdf_without_text_is_reported(tmp_path):
    f = tmp_path / "taranmis.pdf"
    make_blank_pdf(f)
    with pytest.raises(ExtractionError, match="metin yok"):
        extract_text(f)


def test_strip_print_marks_removes_brochure_imprint():
    text = "\n".join(BROCHURE_IMPRINT)
    assert strip_print_marks(text).strip() == ""


def test_strip_print_marks_keeps_real_text():
    text = "\n".join([BROCHURE_IMPRINT[0], "Psikoloji nedir?", *BROCHURE_IMPRINT[1:3], LOREM])
    cleaned = [line for line in strip_print_marks(text).split("\n") if line.strip()]
    assert cleaned == ["Psikoloji nedir?", LOREM]


def test_strip_print_marks_does_not_touch_normal_sentences():
    text = "C vitamini ve K vitamini.\nMy notes about CMY K printing.\nComposite numbers"
    assert strip_print_marks(text) == text


def test_brochure_with_only_imprint_is_skipped(tmp_path):
    f = tmp_path / "brosur.pdf"
    make_text_pdf(f, BROCHURE_IMPRINT)
    with pytest.raises(ExtractionError, match="görsel/çizime dönüştürülmüş"):
        extract_text(f)


def test_pdf_with_too_little_text_is_skipped(tmp_path):
    f = tmp_path / "az.pdf"
    make_text_pdf(f, "Sadece kapak")
    with pytest.raises(ExtractionError, match="metin yok"):
        extract_text(f)


def test_pdf_with_imprint_and_real_text_keeps_text(tmp_path):
    f = tmp_path / "karisik.pdf"
    make_text_pdf(f, [BROCHURE_IMPRINT[0], LOREM, *BROCHURE_IMPRINT[1:3]])
    out = extract_text(f)
    assert LOREM in out
    assert "fh11" not in out and "CMY" not in out and "Composite" not in out


def test_corrupt_pdf_is_reported(tmp_path):
    f = tmp_path / "bozuk.pdf"
    f.write_bytes(b"bu bir pdf degil")
    with pytest.raises(ExtractionError, match="PDF okunamadı"):
        extract_text(f)


def test_password_protected_pdf_is_reported(tmp_path):
    f = tmp_path / "sifreli.pdf"
    make_blank_pdf(f, password="gizli")
    with pytest.raises(ExtractionError, match="şifreli"):
        extract_text(f)


# --- scanning a directory ------------------------------------------------------------


def test_scan_library_collects_and_skips(tmp_path):
    (tmp_path / "alt").mkdir()
    (tmp_path / "a.txt").write_text("birinci", encoding="utf-8")
    (tmp_path / "alt" / "b.md").write_text("# ikinci", encoding="utf-8")
    make_text_pdf(tmp_path / "c.pdf", LOREM)
    make_blank_pdf(tmp_path / "taranmis.pdf")
    (tmp_path / "resim.png").write_bytes(b"\x89PNG")
    (tmp_path / ".mclibrary_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".gizli").mkdir()
    (tmp_path / ".gizli" / "x.txt").write_text("gizli", encoding="utf-8")

    docs, skipped = scan_library(tmp_path)

    assert [d.path.as_posix() for d in docs] == ["a.txt", "alt/b.md", "c.pdf"]
    assert docs[1].text == "ikinci"
    assert len(skipped) == 1
    assert skipped[0].path.as_posix() == "taranmis.pdf"
    assert "metin yok" in skipped[0].reason


def test_scan_library_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_library(tmp_path / "yok")
