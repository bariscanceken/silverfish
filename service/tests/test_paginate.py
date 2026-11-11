import random

import pytest

from mclibrary.paginate import (
    BOOK_MAX_PAGES,
    LINE_MAX_CHARS,
    PAGE_MAX_CHARS,
    PAGE_MAX_LINES,
    TITLE_MAX_CHARS,
    make_volumes,
    paginate,
    split_volumes,
    truncate_title,
    wrap_lines,
)

TURKISH_WORDS = (
    "ağaç ılık şimşek İstanbul çiçek öğretmen ğ ıssız Iğdır kütüphane "
    "değerlendirme sığınak çöp şüphesiz gözlükçü İzmir ölçüsüzlük"
).split()


def rendered_line_count(page: str) -> int:
    return len(wrap_lines(page))


def turkish_document(paragraphs: int, seed: int = 1) -> str:
    rng = random.Random(seed)
    paras = []
    for _ in range(paragraphs):
        words = [rng.choice(TURKISH_WORDS) for _ in range(rng.randint(5, 60))]
        paras.append(" ".join(words))
    return "\n\n".join(paras)


def assert_page_limits(pages: list[str]) -> None:
    for page in pages:
        assert 0 < len(page) <= PAGE_MAX_CHARS, page
        assert rendered_line_count(page) <= PAGE_MAX_LINES, page
        assert page == page.strip("\n"), "page must not start/end with blank lines"


# --- pages ---------------------------------------------------------------------------


def test_short_text_is_one_page():
    assert paginate("Merhaba dünya") == ["Merhaba dünya"]


def test_empty_text_has_no_pages():
    assert paginate("") == []
    assert paginate("\n\n  \n") == []
    assert make_volumes("Boş", "") == []


def test_paragraph_breaks_are_kept():
    assert paginate("Birinci paragraf.\n\nİkinci paragraf.") == [
        "Birinci paragraf.\n\nİkinci paragraf."
    ]


def test_wrapped_lines_are_joined_with_spaces():
    # The game re-wraps, so we must not bake our line breaks into the page.
    text = "bir iki üç dört beş altı yedi sekiz dokuz on"
    assert paginate(text) == [text]


def test_each_line_break_costs_a_line():
    text = "\n".join(f"s{i}" for i in range(30))  # 30 tiny lines, ~90 chars
    pages = paginate(text)
    assert [p.count("\n") + 1 for p in pages] == [14, 14, 2]
    assert "\n".join(pages) == text


def test_blank_lines_count_and_are_trimmed_at_page_edges():
    text = "\n\n".join(f"p{i}" for i in range(10))  # 19 lines incl. blanks
    pages = paginate(text)
    assert_page_limits(pages)
    # Line 14 would be the blank line after "p6": it is trimmed, not carried over.
    assert pages[0] == "p0\n\np1\n\np2\n\np3\n\np4\n\np5\n\np6"
    assert pages[1] == "p7\n\np8\n\np9"


def test_char_limit_and_words_not_split():
    words = [f"kelime{i}" for i in range(300)]
    text = " ".join(words)
    pages = paginate(text)
    assert len(pages) > 1
    assert_page_limits(pages)
    assert " ".join(pages).split() == words  # nothing lost, no word cut


def test_char_limit_is_counted_in_characters_not_bytes():
    # "ş" is 2 bytes in UTF-8; the limit must still be 230 *characters*.
    text = " ".join(["şşşş"] * 200)
    pages = paginate(text, page_lines=1000)
    assert max(len(p) for p in pages) > PAGE_MAX_CHARS // 2 + 10
    assert all(len(p) <= PAGE_MAX_CHARS for p in pages)


def test_long_word_is_split():
    url = "https://example.com/" + "çok-uzun-bir-yol/" * 20
    pages = paginate(f"Bağlantı: {url} son.")
    assert_page_limits(pages)
    lines = wrap_lines(f"Bağlantı: {url} son.")
    assert all(len(l.text) <= LINE_MAX_CHARS for l in lines)
    assert "".join(pages).replace("\n", "").replace(" ", "") == f"Bağlantı:{url}son."


def test_long_word_longer_than_a_page():
    word = "ğ" * (PAGE_MAX_CHARS * 3)
    pages = paginate(word)
    assert_page_limits(pages)
    assert "".join(pages) == word


def test_turkish_characters_preserved():
    text = turkish_document(40)
    pages = paginate(text)
    assert_page_limits(pages)
    assert " ".join(pages).split() == text.split()
    joined = "".join(pages)
    for ch in "şğıİçöüŞĞÇÖÜ":
        if ch in text:
            assert ch in joined


def test_invalid_limits():
    with pytest.raises(ValueError):
        paginate("x", page_chars=10, line_chars=20)
    with pytest.raises(ValueError):
        paginate("x", page_lines=0)


# --- titles and volumes --------------------------------------------------------------


def test_truncate_title():
    assert truncate_title("Kısa", 32) == "Kısa"
    long = "Çok Uzun Bir Belge Başlığı Örneği İçin Yazıldı"
    out = truncate_title(long, 32)
    assert len(out) == 32 and out.endswith("…")
    assert truncate_title("  çok   boşluklu  ", 32) == "çok boşluklu"


def test_single_volume_keeps_plain_title():
    vols = split_volumes("Şiirler", ["a"] * 100)
    assert len(vols) == 1
    assert vols[0].title == "Şiirler"
    assert (vols[0].number, vols[0].total) == (1, 1)


def test_volumes_split_at_100_pages():
    vols = split_volumes("Ağaçlar", [f"s{i}" for i in range(250)])
    assert [len(v.pages) for v in vols] == [100, 100, 50]
    assert [v.title for v in vols] == ["Ağaçlar (1/3)", "Ağaçlar (2/3)", "Ağaçlar (3/3)"]
    assert vols[2].pages[0] == "s200"


def test_volume_titles_never_exceed_limit():
    name = "İstanbul Kütüphanesinin Çok Uzun Adlı Belgesi"
    for page_count in (101, 999, 1200):
        vols = split_volumes(name, ["x"] * page_count)
        for v in vols:
            assert len(v.title) <= TITLE_MAX_CHARS, v.title
            assert v.title.endswith(f"({v.number}/{v.total})")
    assert split_volumes(name, ["x"] * 1200)[9].title.endswith("… (10/12)")


def test_empty_title_falls_back():
    assert split_volumes("   ", ["x"])[0].title == "Belge"


def test_long_turkish_document_end_to_end():
    text = turkish_document(1500, seed=7)
    vols = make_volumes("Uzun Türkçe Belge", text)
    assert len(vols) >= 3
    assert all(len(v.pages) <= BOOK_MAX_PAGES for v in vols)
    assert all(len(v.pages) == BOOK_MAX_PAGES for v in vols[:-1])
    assert all(len(v.title) <= TITLE_MAX_CHARS for v in vols)
    all_pages = [p for v in vols for p in v.pages]
    assert_page_limits(all_pages)
    assert " ".join(all_pages).split() == text.split()
