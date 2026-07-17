from manga_panels.detect import XYCutDetector, get_detector
import manga_panels.ml as ml


def test_xycut_warmup_is_noop():
    XYCutDetector().warmup()          # does not raise, loads nothing


def test_magi_warmup_calls_load(monkeypatch):
    called = []
    monkeypatch.setattr(ml, "_load_magi", lambda: called.append(True))
    get_detector("ml").warmup()
    assert called == [True]
