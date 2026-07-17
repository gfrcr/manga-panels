import zipfile
from pathlib import Path
from PIL import Image
from manga_panels.archive import unpack, pack


def _make_cbz(path: Path, n: int) -> None:
    with zipfile.ZipFile(path, "w") as z:
        for i in range(n):
            img = Image.new("RGB", (10, 10), (i * 10, 0, 0))
            p = path.parent / f"tmp_{i}.png"
            img.save(p)
            z.write(p, f"{i:03d}.png")
            p.unlink()


def test_unpack_reads_pages_in_order(tmp_path):
    cbz = tmp_path / "ch.cbz"
    _make_cbz(cbz, 3)
    pages = unpack(cbz)
    assert len(pages) == 3
    assert pages[0].size == (10, 10)
    assert pages[0].mode == "RGB"


def test_unpack_natural_sort_non_padded(tmp_path):
    import zipfile
    from PIL import Image
    cbz = tmp_path / "np.cbz"
    order = [1, 2, 10, 11]           # lexicographic would give 1,10,11,2
    with zipfile.ZipFile(cbz, "w") as z:
        for i in order:
            img = Image.new("RGB", (4, 4), (i, 0, 0))   # red channel = page number
            p = tmp_path / f"p{i}.png"
            img.save(p); z.write(p, f"{i}.png"); p.unlink()
    pages = unpack(cbz)
    reds = [px.getpixel((0, 0))[0] for px in pages]
    assert reds == [1, 2, 10, 11]


def test_pack_roundtrip_jpeg_default(tmp_path):
    imgs = [Image.new("RGB", (8, 8), (0, i * 5, 0)) for i in range(4)]
    out = tmp_path / "out.cbz"
    pack(imgs, out)                      # default = jpeg
    with zipfile.ZipFile(out) as z:
        names = sorted(z.namelist())
    assert names == ["0001.jpg", "0002.jpg", "0003.jpg", "0004.jpg"]
    assert len(unpack(out)) == 4


def test_pack_png_format(tmp_path):
    imgs = [Image.new("RGB", (8, 8), (0, 0, 0)) for _ in range(2)]
    out = tmp_path / "out.cbz"
    pack(imgs, out, fmt="png")
    with zipfile.ZipFile(out) as z:
        assert sorted(z.namelist()) == ["0001.png", "0002.png"]


def test_jpeg_quality_knob_affects_size(tmp_path):
    # menor qualidade -> menor arquivo (prova que --quality esta ligado)
    import numpy as np
    arr = np.random.default_rng(0).integers(0, 256, (128, 128, 3), dtype="uint8")
    img = Image.fromarray(arr, "RGB")
    lo = tmp_path / "lo.cbz"; hi = tmp_path / "hi.cbz"
    pack([img], lo, fmt="jpeg", quality=30)
    pack([img], hi, fmt="jpeg", quality=95)
    assert lo.stat().st_size < hi.stat().st_size


def test_pack_bad_format_raises(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        pack([Image.new("RGB", (4, 4))], tmp_path / "x.cbz", fmt="webp")


def test_pack_max_width_downscales_wide(tmp_path):
    wide = Image.new("RGB", (2000, 1000), (10, 20, 30))
    out = tmp_path / "o.cbz"
    pack([wide], out, max_width=800)
    assert unpack(out)[0].size == (800, 400)      # proporcao mantida


def test_pack_max_width_leaves_narrow_untouched(tmp_path):
    narrow = Image.new("RGB", (500, 900), (0, 0, 0))
    out = tmp_path / "o.cbz"
    pack([narrow], out, max_width=800)
    assert unpack(out)[0].size == (500, 900)      # nunca amplia


def test_pack_max_width_none_keeps_size(tmp_path):
    im = Image.new("RGB", (2000, 1000), (0, 0, 0))
    out = tmp_path / "o.cbz"
    pack([im], out)                                # default = sem limite
    assert unpack(out)[0].size == (2000, 1000)


def test_unpack_empty_archive_raises(tmp_path):
    import pytest, zipfile
    from manga_panels.errors import EmptyArchive
    cbz = tmp_path / "empty.cbz"
    with zipfile.ZipFile(cbz, "w") as z:
        z.writestr("leiame.txt", "sem imagens")
    with pytest.raises(EmptyArchive):
        unpack(cbz)


def test_unpack_corrupt_archive_raises(tmp_path):
    import pytest
    from manga_panels.errors import BadArchive
    cbz = tmp_path / "bad.cbz"
    cbz.write_bytes(b"nao sou um zip")
    with pytest.raises(BadArchive):
        unpack(cbz)
