import manga_panels.ml as ml


def test_magi_warmup_calls_load(monkeypatch):
    called = []
    monkeypatch.setattr(ml, "_load_magi", lambda: called.append(True))
    ml.MagiDetector().warmup()
    assert called == [True]
