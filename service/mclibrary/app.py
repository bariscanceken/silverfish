"""HTTP API used by the Fabric mod.

Start with:  uvicorn --factory mclibrary.app:create_app --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import Settings
from .extract import Document, SkippedFile, scan_library
from .paginate import make_volumes
from .state import StateError, StateStore

log = logging.getLogger(__name__)

# 16 hex chars of SHA-256 of the extracted text, then "-" and volume number.
VOLUME_ID_PATTERN = r"^[0-9a-f]{16}-[1-9][0-9]*$"
_VOLUME_ID_RE = re.compile(VOLUME_ID_PATTERN)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def volume_id(text: str, number: int) -> str:
    return f"{content_hash(text)}-{number}"


# --- API models ----------------------------------------------------------------------


class BookOut(BaseModel):
    id: str
    title: str
    author: str
    pages: list[str]


class SkippedOut(BaseModel):
    file: str
    reason: str


class PlanOut(BaseModel):
    books: list[BookOut]
    skipped: list[SkippedOut]


class OnayIn(BaseModel):
    ids: list[str] = Field(max_length=10_000)


class OnayOut(BaseModel):
    accepted: int  # newly recorded ids
    already_delivered: int  # ids that were recorded before


class HealthOut(BaseModel):
    status: str
    library_dir: str
    library_dir_exists: bool


# --- planning ------------------------------------------------------------------------


@dataclass(frozen=True)
class Plan:
    books: list[BookOut]
    skipped: list[SkippedFile]


def build_plan(documents: list[Document], skipped: list[SkippedFile], author: str,
               delivered: set[str]) -> Plan:
    books: list[BookOut] = []
    seen: set[str] = set()
    for doc in documents:
        for vol in make_volumes(doc.path.stem, doc.text):
            vid = volume_id(doc.text, vol.number)
            # Identical content in two files yields the same ids: offer it once.
            if vid in delivered or vid in seen:
                continue
            seen.add(vid)
            books.append(BookOut(id=vid, title=vol.title, author=author, pages=vol.pages))
    return Plan(books, skipped)


# --- app -----------------------------------------------------------------------------


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = StateStore.in_library(settings.library_dir)
    app = FastAPI(title="silverfish-mclibrary")

    @app.get("/saglik", response_model=HealthOut)
    def saglik() -> HealthOut:
        return HealthOut(
            status="ok",
            library_dir=str(settings.library_dir),
            library_dir_exists=settings.library_dir.is_dir(),
        )

    @app.post("/plan", response_model=PlanOut)
    def plan() -> PlanOut:
        try:
            documents, skipped = scan_library(settings.library_dir)
        except FileNotFoundError:
            raise HTTPException(503, f"LIBRARY_DIR klasörü bulunamadı: {settings.library_dir}")
        try:
            delivered = store.delivered_ids()
        except StateError as exc:
            raise HTTPException(500, str(exc))
        result = build_plan(documents, skipped, settings.author, delivered)
        return PlanOut(
            books=result.books,
            skipped=[SkippedOut(file=s.path.as_posix(), reason=s.reason) for s in result.skipped],
        )

    @app.post("/onay", response_model=OnayOut)
    def onay(body: OnayIn) -> OnayOut:
        bad = [i for i in body.ids if not _VOLUME_ID_RE.match(i)]
        if bad:
            raise HTTPException(422, f"geçersiz kitap id'si: {bad[:5]}")
        unique = list(dict.fromkeys(body.ids))
        try:
            accepted = store.mark_delivered(unique)
        except StateError as exc:
            raise HTTPException(500, str(exc))
        return OnayOut(accepted=accepted, already_delivered=len(unique) - accepted)

    return app
