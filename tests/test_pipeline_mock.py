"""End-to-end pipeline in offline mock mode — no models, no network."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from _groupphoto_tools import pipeline


@pytest.fixture()
def photo(tmp_path):
    """A textured RGB JPEG so glare/tone/sharpen have real signal."""
    from PIL import Image
    rng = np.random.default_rng(11)
    p = tmp_path / "group.jpg"
    Image.fromarray(rng.integers(0, 256, (400, 600, 3)).astype("uint8")).save(p)
    return p


def test_enhance_group_tiff_one_output(photo, tmp_path):
    out = tmp_path / "out"
    s = pipeline.enhance_group(photo, out, use_mock=True, out_format="tiff")
    op = Path(s["output"])
    assert op.is_file() and op.suffix == ".tif"
    assert s["n_people"] == 4                     # mock detector
    assert s["face_backend"] == "none"            # mock face-restore passthrough
    assert s["background"] == "none"
    import tifffile
    a = tifffile.imread(op)
    assert a.dtype == np.uint16 and a.shape == (400, 600, 3)


def test_enhance_group_jpg_output(photo, tmp_path):
    from PIL import Image
    out = tmp_path / "outj"
    s = pipeline.enhance_group(photo, out, use_mock=True, out_format="jpg")
    op = Path(s["output"])
    assert op.suffix == ".jpg"
    assert Image.open(op).mode == "RGB"


def test_enhance_group_background_blur(photo, tmp_path):
    out = tmp_path / "outb"
    s = pipeline.enhance_group(photo, out, use_mock=True, out_format="jpg",
                               background="blur")
    assert s["background"] == "blur"
    assert Path(s["output"]).is_file()


def test_enhance_group_no_detect(photo, tmp_path):
    out = tmp_path / "outn"
    s = pipeline.enhance_group(photo, out, use_mock=True, out_format="jpg",
                               detect_people=False)
    assert s["n_people"] == 0
    assert Path(s["output"]).is_file()
