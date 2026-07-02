"""Glare & highlight correction for group photos.

Three physically-distinct cases, sorted by how recoverable they are:

  (a) **Veiling glare / sun haze** — a low-contrast bright veil over the frame. This
      is *not lost data*, just reduced contrast, so it is genuinely fixable. Handled
      here by CLAHE local-contrast (``clahe_local``) + an optional dark-channel-prior
      dehaze (``dehaze_dcp``); the pipeline's global black/white-point ``dehaze16``
      does the rest.

  (b) **Blown windows / sky behind the group** — best recovered *at RAW decode* via
      LibRaw highlight modes (``images.load_image16(highlight_mode=...)``), which
      reconstruct from any channel that stayed below clipping. Fully-clipped regions
      carry no data and are only hideable by inpainting (phase 2). No pixels are
      invented here.

  (c) **Specular reflections** (skin shine, eyeglass glint) — inpaint-based removal is
      phase 2, and glasses that fully occlude the eyes are intentionally left alone
      (inpainting would fabricate eyes). Not done here.

All ops are 16-bit (``uint16`` HxWx3, float32 internally) to match the pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("groupphoto.glare")

_LUMA = (0.299, 0.587, 0.114)


def clahe_local(arr: Any, *, clip: float = 2.0, grid: int = 8) -> Any:
    """Contrast-Limited Adaptive Histogram Equalization on the luminance channel,
    re-applied to RGB as a gain so colour is preserved. Lifts a veiling glare's
    local contrast without the global-clip risk of a full histogram stretch.
    16-bit throughout (cv2 CLAHE supports uint16). No-op-safe."""
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    a = arr.astype(np.float32)
    lw = np.asarray(_LUMA, np.float32)
    lum = np.clip(a @ lw, 0, 65535).astype(np.uint16)
    clahe = cv2.createCLAHE(clipLimit=float(clip), tileGridSize=(grid, grid))
    lum2 = clahe.apply(lum).astype(np.float32)
    gain = lum2 / np.maximum(lum.astype(np.float32), 1.0)
    out = np.clip(a * gain[..., None], 0, 65535).astype(np.uint16)
    log.info("glare: CLAHE local-contrast (clip %.1f, grid %d)", clip, grid)
    return out


def _dark_channel(img01: Any, patch: int) -> Any:
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    mn = img01.min(axis=2)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (patch, patch))
    return cv2.erode(mn, k)


def dehaze_dcp(arr: Any, *, omega: float = 0.85, tmin: float = 0.2,
               patch: int = 15, strength: float = 1.0) -> Any:
    """Dark-Channel-Prior dehaze — the classic single-image haze/veil remover.
    Estimates the atmospheric veil and pulls it back out. ``strength`` (0..1) blends
    the result toward the original so it can be dialled down (DCP can over-darken
    faces at full strength). Opt-in; 16-bit in/out. Requires cv2."""
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    I = arr.astype(np.float32) / 65535.0
    dark = _dark_channel(I, patch)
    # atmospheric light: brightest 0.1% of the dark channel
    flat = dark.reshape(-1)
    n = max(1, int(flat.size * 0.001))
    idx = np.argpartition(flat, -n)[-n:]
    A = I.reshape(-1, 3)[idx].max(axis=0)                      # per-channel veil colour
    A = np.maximum(A, 1e-3)
    t = 1.0 - omega * _dark_channel(I / A, patch)
    t = cv2.blur(t, (patch, patch))                            # cheap transmission refine
    t = np.clip(t, tmin, 1.0)[..., None]
    J = (I - A) / t + A
    J = np.clip(J, 0, 1)
    out = (1.0 - strength) * I + strength * J
    log.info("glare: DCP dehaze (omega %.2f, strength %.2f)", omega, strength)
    return np.clip(out * 65535.0, 0, 65535).astype(np.uint16)


def correct_glare(arr: Any, *, clahe: bool = True, clahe_clip: float = 2.0,
                  dcp: bool = False, dcp_strength: float = 0.7) -> Any:
    """Orchestrate the recoverable-glare path: optional DCP dehaze (strong, opt-in)
    then CLAHE local-contrast (mild, default on). Global black/white-point and
    highlight recovery live elsewhere (pipeline ``dehaze16`` / load ``highlight_mode``)."""
    out = arr
    if dcp:
        out = dehaze_dcp(out, strength=dcp_strength)
    if clahe:
        out = clahe_local(out, clip=clahe_clip)
    return out
