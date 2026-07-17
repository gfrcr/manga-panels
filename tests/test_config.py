import pytest
from manga_panels.config import load_config
from manga_panels.errors import MangaPanelsError
import manga_panels.config as config


def test_reads_defaults(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[defaults]\ndetector = "ml"\nmax_width = 1264\n')
    assert load_config(str(cfg)) == {"detector": "ml", "max_width": 1264}


def test_unknown_key_ignored_with_warning(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[defaults]\ndetector = "ml"\nbogus = 1\n')
    warned = []
    assert load_config(str(cfg), warn=warned.append) == {"detector": "ml"}
    assert warned                      # avisou sobre a chave desconhecida


def test_hyphen_key_normalized(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[defaults]\nkeep-first = 2\n')
    assert load_config(str(cfg)) == {"keep_first": 2}


def test_missing_explicit_raises(tmp_path):
    with pytest.raises(MangaPanelsError):
        load_config(str(tmp_path / "nope.toml"))


def test_bad_toml_raises(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text("isto = = nao e toml")
    with pytest.raises(MangaPanelsError):
        load_config(str(cfg))


def test_no_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DISCOVER", [tmp_path / "manga-panels.toml"])
    assert load_config(None) == {}     # nenhum arquivo -> sem defaults
