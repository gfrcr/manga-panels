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


def test_pack_roundtrip(tmp_path):
    imgs = [Image.new("RGB", (8, 8), (0, i * 5, 0)) for i in range(4)]
    out = tmp_path / "out.cbz"
    pack(imgs, out)
    with zipfile.ZipFile(out) as z:
        names = sorted(z.namelist())
    assert names == ["0001.png", "0002.png", "0003.png", "0004.png"]
    assert len(unpack(out)) == 4
