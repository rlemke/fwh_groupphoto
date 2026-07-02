"""Background matting + composite (mock matte, no models)."""

from __future__ import annotations

import numpy as np

from _groupphoto_tools import background as bg


def _img(h=200, w=300):
    rng = np.random.default_rng(9)
    return rng.integers(0, 65536, (h, w, 3)).astype(np.uint16)


def test_mock_matte_is_uint8_mask():
    arr = _img()
    alpha = bg.matte(arr, use_mock=True)
    assert alpha.dtype == np.uint8 and alpha.shape == arr.shape[:2]
    assert alpha.max() == 255 and alpha.min() == 0     # central band + empty edges


def test_composite_blur_changes_background_keeps_shape():
    arr = _img()
    alpha = bg.matte(arr, use_mock=True)
    out = bg.composite(arr, alpha, mode="blur")
    assert out.dtype == np.uint16 and out.shape == arr.shape
    # a corner is background (alpha 0) → should differ from the original there
    assert not np.array_equal(out[:20, :20], arr[:20, :20])
    # centre is foreground (alpha 255) → essentially unchanged
    cy, cx = arr.shape[0] // 2, arr.shape[1] // 2
    assert np.allclose(out[cy, cx], arr[cy, cx], atol=300)


def test_composite_color_fills_background():
    arr = _img()
    alpha = bg.matte(arr, use_mock=True)
    out = bg.composite(arr, alpha, mode="color", color="white", feather=0)
    assert (out[:10, :10] > 64000).all()               # white bg in the corner


def test_replace_background_none_is_noop():
    arr = _img()
    out, info = bg.replace_background(arr, mode="none")
    assert info["background"] == "none" and np.array_equal(out, arr)


def test_replace_background_blur_mock():
    arr = _img()
    out, info = bg.replace_background(arr, mode="blur", use_mock=True)
    assert info["background"] == "blur"
    assert not np.array_equal(out[:20, :20], arr[:20, :20])
