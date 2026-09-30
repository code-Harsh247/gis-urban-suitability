"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from src.synthetic import make_synthetic_project


@pytest.fixture(scope="session")
def synthetic_project(tmp_path_factory):
    """A 20 × 20-cell fake project with stub files for every contract (C1–C8).

    Session-scoped and shared: tests must not modify its files. Copy what you
    need, or call ``make_synthetic_project(tmp_path)`` for a private one.
    """
    return make_synthetic_project(tmp_path_factory.mktemp("synthetic"))
