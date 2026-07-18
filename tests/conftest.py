import pytest

import manga_panels.config as config


@pytest.fixture(autouse=True)
def _no_ambient_config(monkeypatch):
    """Keep tests hermetic: never auto-discover a real manga-panels.toml on the
    machine (a global [defaults] would otherwise leak in)."""
    monkeypatch.setattr(config, "_DISCOVER", [])


def _fake_boxes(page):
    """Deterministic panel boxes: one per black blob on the page (grid -> 4,
    single -> 1, blank -> 0)."""
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
    boxes.sort(key=lambda b: (b[1], -b[0]))     # rough manga order
    return boxes


def _fake_raw(self, page):
    """Stand-in for Magi's full output: panels from black blobs, no text/chars.
    detect() and the debug overlay both go through detect_raw, so mocking this
    keeps pipeline/CLI/debug tests offline."""
    panels = [[x, y, x + w, y + h] for (x, y, w, h) in _fake_boxes(page)]
    return {"panels": panels, "texts": [], "characters": [], "tails": [],
            "text_character_associations": [], "text_tail_associations": [],
            "character_cluster_labels": [], "is_essential_text": []}


@pytest.fixture(autouse=True)
def _fake_magi(request, monkeypatch):
    """Mock Magi so pipeline/CLI/debug tests run offline and fast (no 1.5GB model).
    Skipped for test_ml.py (tests the ml internals) and @pytest.mark.ml."""
    if request.module.__name__.endswith("test_ml") or "ml" in request.keywords:
        return
    import manga_panels.ml as ml
    monkeypatch.setattr(ml, "_load_magi", lambda: object())        # warmup: no real load
    monkeypatch.setattr(ml.MagiDetector, "detect_raw", _fake_raw)  # deterministic output
