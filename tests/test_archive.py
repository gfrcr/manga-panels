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


def test_unpack_single_image(tmp_path):
    p = tmp_path / "page.png"
    Image.new("RGB", (30, 40), (0, 0, 0)).save(p)
    pages = unpack(p)
    assert len(pages) == 1
    assert pages[0].size == (30, 40) and pages[0].mode == "RGB"


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
    # lower quality -> smaller file (proves --quality is wired up)
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
    assert unpack(out)[0].size == (800, 400)      # aspect ratio preserved


def test_pack_max_width_leaves_narrow_untouched(tmp_path):
    narrow = Image.new("RGB", (500, 900), (0, 0, 0))
    out = tmp_path / "o.cbz"
    pack([narrow], out, max_width=800)
    assert unpack(out)[0].size == (500, 900)      # never upscales


def test_pack_max_width_none_keeps_size(tmp_path):
    im = Image.new("RGB", (2000, 1000), (0, 0, 0))
    out = tmp_path / "o.cbz"
    pack([im], out)                                # default = no limit
    assert unpack(out)[0].size == (2000, 1000)


def test_unpack_empty_archive_raises(tmp_path):
    import pytest, zipfile
    from manga_panels.errors import EmptyArchive
    cbz = tmp_path / "empty.cbz"
    with zipfile.ZipFile(cbz, "w") as z:
        z.writestr("readme.txt", "no images")
    with pytest.raises(EmptyArchive):
        unpack(cbz)


def test_unpack_corrupt_archive_raises(tmp_path):
    import pytest
    from manga_panels.errors import BadArchive
    cbz = tmp_path / "bad.cbz"
    cbz.write_bytes(b"not a zip")
    with pytest.raises(BadArchive):
        unpack(cbz)


def test_pack_atomic_no_partial_file_on_failure(tmp_path):
    import pytest

    class _Boom:                                   # an "image" that blows up on save
        def save(self, *a, **k):
            raise RuntimeError("boom")

    out = tmp_path / "o.cbz"
    with pytest.raises(RuntimeError):
        pack([Image.new("RGB", (4, 4)), _Boom()], out)
    assert not out.exists()                        # atomic: never a half-written cbz
    assert not (tmp_path / "o.cbz.tmp").exists()   # temp cleaned up


def test_unpack_corrupt_entry_data_raises(tmp_path):
    import io, pytest, zipfile
    from PIL import Image
    from manga_panels.errors import BadArchive
    cbz = tmp_path / "corrupt_entry.cbz"
    buf = io.BytesIO(); Image.new("RGB", (20, 20), (200, 0, 0)).save(buf, "PNG")
    with zipfile.ZipFile(cbz, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("0001.png", buf.getvalue())
    data = bytearray(cbz.read_bytes())
    for i in range(50, 90):            # corrupt the middle of the deflate stream
        data[i] ^= 0xFF
    cbz.write_bytes(data)
    with pytest.raises(BadArchive):    # wrapped zlib.error, not a raw traceback
        unpack(cbz)
