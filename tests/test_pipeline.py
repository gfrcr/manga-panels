import zipfile
import numpy as np
from pathlib import Path
from PIL import Image
from manga_panels.pipeline import crop_panels, process_archive
from manga_panels.archive import pack, unpack


def _grid_page():
    arr = np.full((200, 200), 255, np.uint8)
    for (y, x) in [(20, 20), (20, 120), (120, 20), (120, 120)]:
        arr[y:y + 60, x:x + 60] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def test_crop_returns_subimages():
    page = _grid_page()
    panels = crop_panels(page, [(20, 20, 60, 60), (120, 20, 60, 60)])
    assert [p.size for p in panels] == [(60, 60), (60, 60)]


def test_process_archive_explodes_panels(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)                     # 1 page, 4 panels
    out = tmp_path / "ch_panels.cbz"
    n = process_archive(src, out, page_pos="off")
    assert n == 4
    with zipfile.ZipFile(out) as z:
        assert len(z.namelist()) == 4


def test_process_archive_prepends_full_page(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)                     # 1 page 200x200, 4 panels
    out = tmp_path / "ch_panels.cbz"
    n = process_archive(src, out)                 # page_pos default = before
    assert n == 5                                 # full page + 4 panels
    imgs = unpack(out)
    assert imgs[0].size == (200, 200)             # macro first
    assert all(im.size != (200, 200) for im in imgs[1:])


def test_include_page_not_duplicated_when_whole_page(tmp_path):
    src = tmp_path / "blank.cbz"
    pack([Image.new("RGB", (100, 100), (255, 255, 255))], src)
    out = tmp_path / "out.cbz"
    assert process_archive(src, out) == 1         # 0 panels -> page once


def _single_panel_page():
    # white page with ONE black rectangle and no internal gutter -> 1 panel
    arr = np.full((200, 200), 255, np.uint8)
    arr[40:160, 40:160] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def test_single_panel_page_emitted_once(tmp_path):
    src = tmp_path / "sp.cbz"
    pack([_single_panel_page()], src)
    out = tmp_path / "out.cbz"
    assert process_archive(src, out) == 1         # 1 panel ~ page -> no duplicate


def test_page_pos_after_puts_macro_last(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    out = tmp_path / "out.cbz"
    n = process_archive(src, out, page_pos="after")
    assert n == 5
    imgs = unpack(out)
    assert imgs[-1].size == (200, 200)            # macro last
    assert imgs[0].size != (200, 200)             # panel first


def test_process_archive_bad_page_pos_raises(tmp_path):
    import pytest
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    with pytest.raises(ValueError):
        process_archive(src, tmp_path / "o.cbz", page_pos="nope")


def test_keep_first_keeps_pages_whole(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page(), _grid_page()], src)       # 2 pages of 4 panels
    out = tmp_path / "out.cbz"
    n = process_archive(src, out, keep_first=1)   # 1st whole, 2nd cropped
    assert n == 6                                 # 1 (whole) + 5 (macro+4)
    imgs = unpack(out)
    assert imgs[0].size == (200, 200)             # 1st page whole, uncropped


def test_blank_page_falls_back_to_whole_page(tmp_path):
    src = tmp_path / "blank.cbz"
    pack([Image.new("RGB", (100, 100), (255, 255, 255))], src)
    out = tmp_path / "blank_panels.cbz"
    n = process_archive(src, out)
    assert n == 1                                  # never loses the page


def test_cli_processes_folder(tmp_path):
    from manga_panels.cli import main
    from manga_panels.archive import pack
    src_dir = tmp_path / "chapters"
    src_dir.mkdir()
    pack([_grid_page()], src_dir / "c1.cbz")
    out_dir = tmp_path / "out"
    rc = main([str(src_dir), "-o", str(out_dir)])
    assert rc == 0
    assert (out_dir / "c1_panels.cbz").exists()


def test_cli_empty_folder_does_not_create_output_dir(tmp_path):
    from manga_panels.cli import main
    empty_dir = tmp_path / "chapters"
    empty_dir.mkdir()
    out = tmp_path / "out"
    rc = main([str(empty_dir), "-o", str(out)])
    assert rc != 0
    assert not out.exists()


def test_cli_same_stem_different_ext_no_overwrite(tmp_path):
    from manga_panels.cli import main
    from manga_panels.archive import pack
    src_dir = tmp_path / "chapters"
    src_dir.mkdir()
    pack([_grid_page()], src_dir / "c1.cbz")
    pack([_grid_page()], src_dir / "c1.zip")
    out_dir = tmp_path / "out"
    rc = main([str(src_dir), "-o", str(out_dir)])
    assert rc == 0
    outputs = sorted(out_dir.iterdir())
    assert len(outputs) == 2
    for f in outputs:
        assert f.stat().st_size > 0
        with zipfile.ZipFile(f) as z:
            assert len(z.namelist()) == 5   # full page + 4 panels (--page default)


def test_cli_bracket_filename_does_not_crash(tmp_path):
    # real manga names use brackets ([c01], [web]); "/" never appears in a file
    # name (it's the OS path separator), so Rich's closing tag ([/x]) only reaches
    # us intact via another non-filesystem sink: an unknown key in the config toml.
    from manga_panels.cli import main
    src = tmp_path / "chapter [c01] [web].cbz"   # brackets look like Rich markup
    pack([_grid_page()], src)
    cfg = tmp_path / "manga-panels.toml"
    cfg.write_text('[defaults]\n"weird [c01] [/x]" = true\n')  # unknown key -> warn()
    rc = main([str(src), "--config", str(cfg)])   # must not raise MarkupError
    assert rc == 0
    assert (tmp_path / "chapter [c01] [web]_panels.cbz").exists()


def test_cli_magi_load_failure_reported_without_raising(tmp_path, monkeypatch):
    from manga_panels.cli import main
    import manga_panels.ml as ml

    def _boom():
        from manga_panels.errors import MissingDependency
        raise MissingDependency("failed to import torch/transformers")

    monkeypatch.setattr(ml, "_load_magi", _boom)   # warmup blows up
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    rc = main([str(src)])
    assert rc != 0


def test_cli_batch_continues_past_bad_file(tmp_path):
    from manga_panels.cli import main
    src_dir = tmp_path / "in"
    src_dir.mkdir()
    pack([_grid_page()], src_dir / "good.cbz")
    (src_dir / "bad.cbz").write_bytes(b"not a zip")   # will fail to unpack
    out_dir = tmp_path / "out"
    rc = main([str(src_dir), "-o", str(out_dir)])
    assert rc != 0                                     # a file failed
    assert (out_dir / "good_panels.cbz").exists()      # but the good one got through


def test_cli_keyboardinterrupt_exits_clean(tmp_path, monkeypatch):
    from manga_panels.cli import main
    import manga_panels.cli as cli

    def _boom(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "process_archive", _boom)
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    assert main([str(src)]) == 130                     # clean interrupt code, no traceback


def test_entry_exits_with_main_return_code(monkeypatch):
    import signal
    import pytest
    import manga_panels.cli as cli
    monkeypatch.setattr(cli, "main", lambda argv=None: 0)
    old = signal.getsignal(signal.SIGTERM)
    try:
        with pytest.raises(SystemExit) as e:
            cli._entry()
        assert e.value.code == 0
    finally:
        signal.signal(signal.SIGTERM, old)


def test_cli_debug_writes_debug_cbz(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    rc = main([str(src), "--debug"])
    assert rc == 0
    assert (tmp_path / "ch_debug.cbz").exists()
    assert not (tmp_path / "ch_panels.cbz").exists()


def test_cli_preview_writes_preview_cbz(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    rc = main([str(src), "--preview"])
    assert rc == 0
    assert (tmp_path / "ch_preview.cbz").exists()
    assert not (tmp_path / "ch_panels.cbz").exists()


def test_process_archive_on_page_called_per_page(tmp_path):
    calls = []
    src = tmp_path / "ch.cbz"
    pack([_grid_page(), _grid_page()], src)
    process_archive(src, tmp_path / "o.cbz",
                    on_page=lambda done, total: calls.append((done, total)))
    assert calls == [(1, 2), (2, 2)]


def test_cli_no_input_no_library_errors(monkeypatch):
    import manga_panels.config as config
    monkeypatch.setattr(config, "_DISCOVER", [])   # ignore any stray toml in cwd
    from manga_panels.cli import main
    assert main([]) != 0


def test_cli_no_input_uses_library_picker(tmp_path, monkeypatch):
    import manga_panels.config as config
    import manga_panels.browse as browse
    monkeypatch.setattr(config, "_DISCOVER", [])
    src = tmp_path / "Vol.01.cbz"
    pack([_grid_page()], src)
    monkeypatch.setattr(browse, "pick_from_library", lambda root, **kw: [src])
    from manga_panels.cli import main
    out_dir = tmp_path / "out"
    rc = main(["--library", str(tmp_path), "-o", str(out_dir)])
    assert rc == 0
    assert (out_dir / "Vol.01_panels.cbz").exists()


def test_process_archive_cover_is_first_page(tmp_path):
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    cover = tmp_path / "cover.png"
    Image.new("RGB", (50, 70), (123, 0, 0)).save(cover)
    out = tmp_path / "out.cbz"
    n = process_archive(src, out, cover=str(cover), page_pos="off")
    imgs = unpack(out)
    assert imgs[0].size == (50, 70)                 # cover is page 1
    assert n == 5                                   # cover + 4 panels


def test_cli_cover(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    cover = tmp_path / "cover.png"
    Image.new("RGB", (50, 70), (9, 9, 9)).save(cover)
    assert main([str(src), "--cover", str(cover)]) == 0
    assert unpack(tmp_path / "ch_panels.cbz")[0].size == (50, 70)


def test_cli_cover_missing_errors(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    assert main([str(src), "--cover", str(tmp_path / "nope.png")]) != 0


def test_cli_grayscale_output(tmp_path):
    import io, zipfile
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    assert main([str(src), "--grayscale"]) == 0
    with zipfile.ZipFile(tmp_path / "ch_panels.cbz") as z:
        raw = Image.open(io.BytesIO(z.read(z.namelist()[0])))
    assert raw.mode == "L"


def test_cli_device_resolves_max_width(tmp_path, monkeypatch):
    from manga_panels.cli import main
    import manga_panels.cli as cli
    captured = {}

    def spy(in_path, out, *, on_page=None, **kw):
        captured.update(kw)
        pack([Image.new("RGB", (4, 4))], out, fmt=kw.get("fmt", "jpeg"))
        return 1

    monkeypatch.setattr(cli, "process_archive", spy)
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    assert main([str(src), "--device", "scribe", "--grayscale"]) == 0
    assert captured["max_width"] == 1860 and captured["grayscale"] is True


def test_cli_format_pdf_writes_pdf(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    rc = main([str(src), "--format", "pdf"])
    assert rc == 0
    out = tmp_path / "ch_panels.pdf"
    assert out.exists() and out.read_bytes()[:5] == b"%PDF-"
    assert not (tmp_path / "ch_panels.cbz").exists()


def test_cli_custom_suffix(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    assert main([str(src), "--suffix", "_cut"]) == 0
    assert (tmp_path / "ch_cut.cbz").exists()


def test_cli_overwrite_replaces_source(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)                       # 1 page -> 4 panels
    assert len(unpack(src)) == 1
    assert main([str(src), "--overwrite"]) == 0
    assert not (tmp_path / "ch_panels.cbz").exists()   # no sibling written
    assert not (tmp_path / "ch.cbz.tmp").exists()      # temp cleaned up
    assert len(unpack(src)) == 5                        # source now holds macro + 4


def test_cli_empty_suffix_refuses_to_clobber_source(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    assert main([str(src), "--suffix", ""]) != 0    # out == source -> refuse
    assert len(unpack(src)) == 1                     # untouched


def test_cli_config_defaults_applied_and_cli_wins(tmp_path):
    from manga_panels.cli import main
    src = tmp_path / "ch.cbz"
    pack([_grid_page()], src)
    cfg = tmp_path / "manga-panels.toml"
    cfg.write_text('[defaults]\nformat = "png"\n')
    # config sets png; no flag -> png output
    out1 = tmp_path / "a.cbz"
    assert main([str(src), "-o", str(out1), "--config", str(cfg)]) == 0
    import zipfile
    with zipfile.ZipFile(out1) as z:
        assert z.namelist()[0].endswith(".png")
    # CLI flag beats the config
    out2 = tmp_path / "b.cbz"
    assert main([str(src), "-o", str(out2), "--config", str(cfg), "-f", "jpeg"]) == 0
    with zipfile.ZipFile(out2) as z:
        assert z.namelist()[0].endswith(".jpg")
