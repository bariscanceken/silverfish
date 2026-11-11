import json
import os

import pytest

from mclibrary.state import STATE_FILENAME, StateError, StateStore


def test_empty_when_missing(tmp_path):
    assert StateStore.in_library(tmp_path).delivered_ids() == set()


def test_mark_and_reload(tmp_path):
    store = StateStore.in_library(tmp_path)
    assert store.mark_delivered(["a-1", "a-2", "a-1"]) == 2
    assert store.mark_delivered(["a-2", "b-1"]) == 1
    # A fresh store reads what the first one wrote.
    assert StateStore.in_library(tmp_path).delivered_ids() == {"a-1", "a-2", "b-1"}
    data = json.loads((tmp_path / STATE_FILENAME).read_text(encoding="utf-8"))
    assert data["version"] == 1 and set(data["delivered"]) == {"a-1", "a-2", "b-1"}


def test_nothing_new_does_not_write(tmp_path):
    store = StateStore.in_library(tmp_path)
    assert store.mark_delivered([]) == 0
    assert not (tmp_path / STATE_FILENAME).exists()


def test_interrupted_write_keeps_old_file(tmp_path, monkeypatch):
    store = StateStore.in_library(tmp_path)
    store.mark_delivered(["a-1"])
    before = (tmp_path / STATE_FILENAME).read_bytes()

    def crash(*args, **kwargs):
        raise OSError("disk yanıt vermiyor")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(StateError, match="yazılamadı"):
        store.mark_delivered(["b-1"])

    assert (tmp_path / STATE_FILENAME).read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == [STATE_FILENAME]  # no temp leftovers


def test_interrupted_by_keyboard_interrupt_cleans_up(tmp_path, monkeypatch):
    store = StateStore.in_library(tmp_path)

    def stop(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "fsync", stop)
    with pytest.raises(KeyboardInterrupt):
        store.mark_delivered(["a-1"])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("content", ["{bozuk", "[]", '{"delivered": []}', "{}"])
def test_corrupt_file_raises_instead_of_resetting(tmp_path, content):
    (tmp_path / STATE_FILENAME).write_text(content, encoding="utf-8")
    with pytest.raises(StateError, match="bozuk"):
        StateStore.in_library(tmp_path).delivered_ids()
