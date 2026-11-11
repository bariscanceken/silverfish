import pytest

from mclibrary.extract import extract_text
from mclibrary.paginate import make_volumes
from mclibrary.reflow import HARD_BREAK, is_list_item, join_wrapped_lines, starts_lowercase

AFAD = (
    "Afet ve Acil Durum Yönetimi Başkanlığı, afet ve acil durumlar ile sivil "
    "savunmaya ilişkin hizmetlerin\nülke düzeyinde etkin bir şekilde "
    "gerçekleştirilmesi için gerekli önlemlerin alınması ve olayların meydana\n"
    "gelmesinden önce hazırlık..."
)


def test_afad_sample_is_joined_into_one_line():
    out = join_wrapped_lines(AFAD)
    assert "\n" not in out
    assert "hizmetlerin ülke düzeyinde" in out
    assert "meydana gelmesinden" in out
    assert out == AFAD.replace("\n", " ")


def test_afad_sample_book_page_has_no_mid_sentence_breaks():
    vols = make_volumes("AFAD", AFAD)
    assert "\n" not in "".join(vols[0].pages)


def test_hyphenated_word_is_rejoined():
    assert join_wrapped_lines("yeniden yapılan-\nması gerekir") == "yeniden yapılanması gerekir"


def test_hyphen_before_capital_is_kept():
    text = "Ankara-\nİstanbul hattı"
    assert join_wrapped_lines(text) == text


@pytest.mark.parametrize("end", [".", "!", "?", ":", "…", "..."])
def test_sentence_end_keeps_break(end):
    text = f"Cümle bitti{end}\nyeni satır"
    assert join_wrapped_lines(text) == text


def test_capital_start_keeps_break():
    text = "Başlık\nBu bir paragraf"
    assert join_wrapped_lines(text) == text


@pytest.mark.parametrize(
    "first, joined",
    [
        ("ıssız", True),  # dotless lowercase ı
        ("işte", True),  # dotted lowercase i
        ("şehir", True),
        ("ğ", True),
        ("Iğdır", False),  # dotless capital I
        ("İzmir", False),  # dotted capital İ
        ("Şile", False),
        ("Çorum", False),
        ("1990 yılında", False),  # digits are not lowercase letters
    ],
)
def test_turkish_case_detection(first, joined):
    text = f"önceki satır\n{first} devam"
    expected = f"önceki satır {first} devam" if joined else text
    assert join_wrapped_lines(text) == expected


def test_starts_lowercase_turkish():
    assert starts_lowercase("ı") and starts_lowercase("  i")
    assert not starts_lowercase("İ") and not starts_lowercase("I")
    assert not starts_lowercase("") and not starts_lowercase("   ")


def test_list_items_are_left_alone():
    text = "Gerekenler\n- su\n• fener\n* düdük\n1. çanta\n2) belge\n– ilaç"
    assert join_wrapped_lines(text) == text
    assert all(is_list_item(l) for l in text.split("\n")[1:])


def test_wrapped_list_item_continuation_is_joined():
    text = "- uzun bir liste öğesi\nalt satıra taşmış\n- ikinci öğe"
    assert join_wrapped_lines(text) == "- uzun bir liste öğesi alt satıra taşmış\n- ikinci öğe"


def test_paragraph_breaks_are_kept():
    text = "birinci paragraf\nsürüyor\n\nikinci paragraf\ndevam ediyor"
    assert join_wrapped_lines(text) == (
        "birinci paragraf sürüyor\n\nikinci paragraf devam ediyor"
    )


def test_never_joins_across_paragraphs():
    text = "satır sonu yok\n\nküçük harfle başlayan paragraf"
    assert join_wrapped_lines(text) == text


POEM_LINES = ["gül dalında", "bülbül öter", "sabah olur", "ışık düşer"]
POEM = "\n".join(POEM_LINES)


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["LF", "CRLF"])
def test_markdown_hard_breaks_keep_poem_lines(tmp_path, newline):
    md = (
        "# Şiir" + newline * 2
        + "gül dalında  " + newline  # two spaces
        + "bülbül öter\\" + newline  # backslash
        + "sabah olur   " + newline  # three spaces
        + "ışık düşer" + newline
    )
    f = tmp_path / "siir.md"
    f.write_bytes(md.encode("utf-8"))
    vols = make_volumes("Şiir", extract_text(f))
    page = vols[0].pages[0]
    assert page == f"Şiir\n\n{POEM}"
    assert "\\" not in page and HARD_BREAK not in page


def test_markdown_without_hard_breaks_is_joined(tmp_path):
    f = tmp_path / "siir.md"
    f.write_text(POEM, encoding="utf-8")
    assert make_volumes("Şiir", extract_text(f))[0].pages == [" ".join(POEM_LINES)]


def test_trailing_spaces_in_txt_are_not_hard_breaks(tmp_path):
    f = tmp_path / "siir.txt"
    f.write_text("gül dalında  \nbülbül öter\\\nsabah olur", encoding="utf-8")
    page = make_volumes("Şiir", extract_text(f))[0].pages[0]
    assert page == "gül dalında bülbül öter\\ sabah olur"


def test_whitespace_only_line_is_not_a_hard_break(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("birinci\n   \nikinci", encoding="utf-8")
    assert make_volumes("A", extract_text(f))[0].pages == ["birinci\n\nikinci"]


def test_dash_as_word_not_list_item():
    # "-" without a following space is not a list marker.
    assert not is_list_item("-5 derece")
