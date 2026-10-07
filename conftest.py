"""All product-state writes and terminal connections are isolated in tests."""
import pytest


@pytest.fixture(autouse=True)
def isolated_product_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ATS_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATS_OFFLINE_RESEARCH", "1")
    monkeypatch.setenv("LIVE_MONEY", "FALSE")
