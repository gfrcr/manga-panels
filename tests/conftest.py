import pytest

import manga_panels.config as config


@pytest.fixture(autouse=True)
def _no_ambient_config(monkeypatch):
    """Keep tests hermetic: never auto-discover a real manga-panels.toml on the
    machine (a global [defaults] with detector='ml' would otherwise leak in)."""
    monkeypatch.setattr(config, "_DISCOVER", [])
