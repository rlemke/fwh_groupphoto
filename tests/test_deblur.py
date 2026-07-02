"""Deblur — unsharp + graceful face-restore passthrough (no models)."""

from __future__ import annotations

import numpy as np

from _groupphoto_tools import deblur


def _soft(h=200, w=300):
    import cv2
    rng = np.random.default_rng(7)
    a = rng.integers(0, 65536, (h, w, 3)).astype(np.uint16)
    return cv2.GaussianBlur(a.astype(np.float32), (0, 0), 3.0).astype(np.uint16)


def test_sharpen_increases_high_freq():
    arr = _soft()
    out = deblur.sharpen(arr, amount=1.0)
    assert out.dtype == np.uint16 and out.shape == arr.shape
    lw = np.array([0.299, 0.587, 0.114], np.float32)
    assert (out.astype(np.float32) @ lw).std() >= (arr.astype(np.float32) @ lw).std()


def test_face_restore_mock_is_passthrough():
    arr = _soft()
    out, fb = deblur.restore_faces(arr, use_mock=True)
    assert fb == "none"
    assert np.array_equal(out, arr)          # nothing invented offline


def test_deblur_mock_reports_backends():
    arr = _soft()
    out, info = deblur.deblur(arr, sharpen_amount=0.8, use_mock=True)
    assert out.dtype == np.uint16
    assert info["face_backend"] == "none"
