"""Glare correction — CLAHE + DCP dehaze on 16-bit arrays (no models)."""

from __future__ import annotations

import numpy as np

from _groupphoto_tools import glare


def _veiled(h=200, w=300):
    """A textured image with a bright low-contrast veil (simulated glare)."""
    rng = np.random.default_rng(5)
    base = rng.integers(8000, 40000, (h, w, 3)).astype(np.float32)
    veil = 20000.0                       # lift + compress = veil
    return np.clip(base * 0.4 + veil, 0, 65535).astype(np.uint16)


def test_clahe_local_shape_dtype():
    arr = _veiled()
    out = glare.clahe_local(arr, clip=2.0)
    assert out.dtype == np.uint16 and out.shape == arr.shape


def test_clahe_increases_contrast():
    arr = _veiled()
    out = glare.clahe_local(arr, clip=3.0)
    # local-contrast enhancement should widen the luminance spread
    lw = np.array([0.299, 0.587, 0.114], np.float32)
    assert (out.astype(np.float32) @ lw).std() > (arr.astype(np.float32) @ lw).std()


def test_dcp_dehaze_pulls_down_veil():
    arr = _veiled()
    out = glare.dehaze_dcp(arr, strength=1.0)
    assert out.dtype == np.uint16 and out.shape == arr.shape
    # removing the veil lowers the (previously lifted) minimum
    assert out.min() < arr.min()


def test_correct_glare_orchestrator():
    arr = _veiled()
    out = glare.correct_glare(arr, clahe=True, dcp=True)
    assert out.dtype == np.uint16 and out.shape == arr.shape
