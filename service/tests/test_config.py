import pytest

from mclibrary.config import DEFAULT_AUTHOR, Settings


def test_reads_dir_and_author(monkeypatch, tmp_path):
    monkeypatch.setenv("LIBRARY_DIR", str(tmp_path))
    monkeypatch.setenv("LIBRARY_AUTHOR", "Ayşe")
    s = Settings.from_env()
    assert s.library_dir == tmp_path
    assert s.author == "Ayşe"


def test_author_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("LIBRARY_DIR", str(tmp_path))
    monkeypatch.delenv("LIBRARY_AUTHOR", raising=False)
    assert Settings.from_env().author == DEFAULT_AUTHOR


def test_missing_dir_raises(monkeypatch):
    monkeypatch.delenv("LIBRARY_DIR", raising=False)
    with pytest.raises(RuntimeError):
        Settings.from_env()
