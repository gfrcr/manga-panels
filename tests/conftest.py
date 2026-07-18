import pytest

import manga_panels.config as config


@pytest.fixture(autouse=True)
def _no_ambient_config(monkeypatch):
    """Keep tests hermetic: never auto-discover a real manga-panels.toml on the
    machine (a global [defaults] would otherwise leak in)."""
    monkeypatch.setattr(config, "_DISCOVER", [])


def _fake_detect(self, page):
    """Deterministic stand-in for Magi: returns a box per black blob on the page.
    Enough for pipeline/CLI tests (grid page -> 4, single -> 1, blank -> 0)."""
    import numpy as np
    from scipy import ndimage

    a = np.asarray(page.convert("L"))
    labeled, n = ndimage.label(a < 128)
    boxes = []
    for i in range(1, n + 1):
        ys, xs = (labeled == i).nonzero()
        if xs.size < 100:                       # skip specks
            continue
        x, y = int(xs.min()), int(ys.min())
        boxes.append((x, y, int(xs.max()) - x + 1, int(ys.max()) - y + 1))
    boxes.sort(key=lambda b: (b[1], -b[0]))     # rough manga order: top->bottom, right->left
    return boxes


@pytest.fixture(autouse=True)
def _fake_magi(request, monkeypatch):
    """Mock Magi so pipeline/CLI tests run offline and fast (no 1.5GB model).
    Skipped for test_ml.py (tests the ml internals) and @pytest.mark.ml."""
    if request.module.__name__.endswith("test_ml") or "ml" in request.keywords:
        return
    import manga_panels.ml as ml
    monkeypatch.setattr(ml, "_load_magi", lambda: object())        # warmup: no real load
    monkeypatch.setattr(ml.MagiDetector, "detect", _fake_detect)   # deterministic boxes
