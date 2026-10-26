from __future__ import annotations

from datetime import datetime

import pytest

from photosorg import fixtures
from photosorg.adapters.memory import MemoryReader, MemoryWriter
from photosorg.config import Config
from photosorg.models import Photo
from photosorg.state import StateStore


@pytest.fixture
def cfg() -> Config:
    return fixtures.demo_config()


@pytest.fixture
def photos() -> list[Photo]:
    return fixtures.demo_photos()


@pytest.fixture
def now() -> datetime:
    return fixtures.DEMO_NOW


@pytest.fixture
def reader(photos: list[Photo]) -> MemoryReader:
    return MemoryReader(photos)


@pytest.fixture
def writer() -> MemoryWriter:
    return MemoryWriter()


@pytest.fixture
def state() -> StateStore:
    store = StateStore(":memory:")
    yield store
    store.close()


def by_label(photos: list[Photo], label: str) -> Photo:
    uuid = fixtures.fake_uuid(label)
    return next(p for p in photos if p.uuid == uuid)
