import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from mclibrary.app import create_app, volume_id
from mclibrary.config import Settings
from mclibrary.paginate import paginate
from mclibrary.reflow import join_wrapped_lines
from mclibrary.state import STATE_FILENAME


@pytest.fixture
def library(tmp_path):
    lib = tmp_path / "kutuphane"
    lib.mkdir()
    return lib


@pytest.fixture
def client(library):
    return TestClient(create_app(Settings(library_dir=library, author="Ayşe")))


def plan(client):
    r = client.post("/plan")
    assert r.status_code == 200, r.text
    return r.json()


def onay(client, ids):
    r = client.post("/onay", json={"ids": ids})
    assert r.status_code == 200, r.text
    return r.json()


def test_saglik(client, library):
    r = client.get("/saglik")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "library_dir": str(library),
        "library_dir_exists": True,
    }


def test_end_to_end_flow(client, library):
    assert plan(client) == {"books": [], "skipped": []}

    # 1) add a file -> it shows up
    (library / "Masal.txt").write_text("Bir varmış, bir yokmuş.", encoding="utf-8")
    books = plan(client)["books"]
    assert len(books) == 1
    book = books[0]
    assert book["title"] == "Masal"
    assert book["author"] == "Ayşe"
    assert book["pages"] == ["Bir varmış, bir yokmuş."]
    assert book["id"] == volume_id("Bir varmış, bir yokmuş.", 1)

    # 2) confirm -> next plan is empty, state file written
    assert onay(client, [book["id"]]) == {"accepted": 1, "already_delivered": 0}
    assert plan(client)["books"] == []
    assert (library / STATE_FILENAME).exists()

    # confirming again is harmless
    assert onay(client, [book["id"]]) == {"accepted": 0, "already_delivered": 1}

    # 3) renaming the file does not bring the book back
    (library / "Masal.txt").rename(library / "Yeni Ad.txt")
    assert plan(client)["books"] == []

    # 4) changing the content does
    (library / "Yeni Ad.txt").write_text("Evvel zaman içinde...", encoding="utf-8")
    books = plan(client)["books"]
    assert [b["title"] for b in books] == ["Yeni Ad"]
    assert books[0]["id"] != book["id"]


def test_state_survives_restart(library):
    (library / "a.txt").write_text("içerik", encoding="utf-8")
    first = TestClient(create_app(Settings(library_dir=library, author="x")))
    onay(first, [plan(first)["books"][0]["id"]])
    second = TestClient(create_app(Settings(library_dir=library, author="x")))
    assert plan(second)["books"] == []


def test_partial_confirmation_of_volumes(client, library):
    # Build a text of 250 pages -> 3 volumes; only 2 fit in the chest.
    page_text = "\n".join(["Kelime"] * 14)  # 14 capitalized lines = one full page
    words = "\n\n".join([page_text] * 250)
    assert len(paginate(join_wrapped_lines(words))) == 250
    (library / "Roman.txt").write_text(words, encoding="utf-8")
    books = plan(client)["books"]
    assert [b["title"] for b in books] == ["Roman (1/3)", "Roman (2/3)", "Roman (3/3)"]
    assert [b["id"].rsplit("-", 1)[1] for b in books] == ["1", "2", "3"]
    assert all(len(b["pages"]) <= 100 for b in books)

    onay(client, [books[0]["id"], books[1]["id"]])
    remaining = plan(client)["books"]
    assert [b["title"] for b in remaining] == ["Roman (3/3)"]


def test_duplicate_content_offered_once(client, library):
    (library / "a.txt").write_text("aynı metin", encoding="utf-8")
    (library / "b.txt").write_text("aynı metin", encoding="utf-8")
    assert len(plan(client)["books"]) == 1


def test_skipped_files_are_reported(client, library):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    (library / "alt").mkdir()
    with (library / "alt" / "tarama.pdf").open("wb") as fh:
        writer.write(fh)
    (library / "bos.txt").write_text("", encoding="utf-8")

    skipped = plan(client)["skipped"]
    assert [s["file"] for s in skipped] == ["alt/tarama.pdf", "bos.txt"]
    assert "metin yok" in skipped[0]["reason"]
    assert skipped[1]["reason"] == "dosya boş"


@pytest.mark.parametrize("ids", [["../../etc"], ["abc"], ["0123456789abcdef-0"]])
def test_onay_rejects_bad_ids(client, ids):
    r = client.post("/onay", json={"ids": ids})
    assert r.status_code == 422


def test_onay_requires_body(client):
    assert client.post("/onay").status_code == 422


def test_missing_library_dir(tmp_path):
    c = TestClient(create_app(Settings(library_dir=tmp_path / "yok", author="x")))
    assert c.get("/saglik").json()["library_dir_exists"] is False
    r = c.post("/plan")
    assert r.status_code == 503
    assert "bulunamadı" in r.json()["detail"]


def test_corrupt_state_is_an_error_not_a_reset(client, library):
    (library / "a.txt").write_text("içerik", encoding="utf-8")
    (library / STATE_FILENAME).write_text("{bozuk", encoding="utf-8")
    r = client.post("/plan")
    assert r.status_code == 500
    assert "bozuk" in r.json()["detail"]


def test_state_file_not_offered_as_book(client, library):
    (library / "a.txt").write_text("içerik", encoding="utf-8")
    onay(client, [plan(client)["books"][0]["id"]])
    assert plan(client) == {"books": [], "skipped": []}
