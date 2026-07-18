from PIL import Image
from manga_panels.debug import annotate_debug


def test_annotate_debug_draws_and_keeps_original():
    page = Image.new("RGB", (200, 200), (255, 255, 255))
    before = page.tobytes()
    r = {"panels": [[10, 10, 90, 90]], "texts": [[20, 20, 60, 40]],
         "characters": [[30, 30, 70, 80]], "tails": [[22, 40, 30, 50]],
         "text_character_associations": [[0, 0]], "text_tail_associations": [[0, 0]],
         "character_cluster_labels": [2], "is_essential_text": [False]}
    out = annotate_debug(page, r)
    assert out.size == (200, 200)
    assert page.tobytes() == before          # original untouched
    assert out.tobytes() != before           # drew the overlay


def test_annotate_debug_handles_empty_result():
    page = Image.new("RGB", (60, 60), (255, 255, 255))
    out = annotate_debug(page, {"panels": []})   # missing keys tolerated
    assert out.size == (60, 60)
