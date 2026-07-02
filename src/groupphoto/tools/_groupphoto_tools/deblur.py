"""Deblur / sharpen for group photos.

Real-world group-photo blur is spatially non-uniform, and the perceptual win is
almost entirely in the **faces** — so the v1 strategy is:

  1. a gentle whole-frame **unsharp** (``sharpen``, 16-bit, always available), then
  2. optional **face restoration** (GFPGAN/CodeFormer via the reused ``enhance``),
     which reconstructs soft faces far better than any global deblur net.

A dedicated global deblur model (NAFNet via ``spandrel_extra_arches``, opt-in
``--deblur``) is phase 2.

Everything stays ``uint16`` (H,W,3). Face restoration runs at 8-bit (the models are
8-bit) and is lifted back to 16-bit — so enabling it trades the final tonal precision
to 8-bit while keeping the array type uniform; the banding-free 16-bit *tone* work
(glare/dehaze/brighten) has already happened upstream. Leave it off to keep true
16-bit end-to-end.
"""

from __future__ import annotations

import logging
from typing import Any

from _groupphoto_tools import enhance as _enhance

log = logging.getLogger("groupphoto.deblur")


def sharpen(arr: Any, *, amount: float = 0.8, radius: float = 2.0) -> Any:
    """Whole-frame unsharp mask (16-bit). ``amount`` is a fraction; 0 disables."""
    return _enhance.unsharp16(arr, radius=radius, amount=amount)


def _to_pil8(arr: Any) -> Any:
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    a8 = np.clip(np.rint(arr.astype(np.float32) / 257.0), 0, 255).astype(np.uint8)
    return Image.fromarray(a8, "RGB")


def _to_arr16(img: Any) -> Any:
    import numpy as np  # noqa: PLC0415
    return (np.asarray(img.convert("RGB"), dtype=np.uint16) * 257)


def restore_faces(arr: Any, *, fidelity: float = 0.7, backend: str = "auto",
                  use_mock: bool = False) -> tuple[Any, str]:
    """Restore every face in the frame (GFPGAN/CodeFormer, multi-face). Returns
    ``(uint16, backend_used)``. Degrades to passthrough when the backend/weights are
    absent (or in mock mode) — same graceful contract as the cycling pipeline."""
    if use_mock:
        return arr, "none"
    img8 = _to_pil8(arr)
    out8, fb = _enhance.restore_faces(img8, fidelity=fidelity, backend=backend)
    if fb == "none":
        return arr, fb                          # nothing changed — keep true 16-bit
    return _to_arr16(out8), fb


def deblur(arr: Any, *, sharpen_amount: float = 0.8, face_restore: bool = True,
           fidelity: float = 0.7, face_backend: str = "auto",
           use_mock: bool = False) -> tuple[Any, dict[str, Any]]:
    """Whole-frame sharpen + optional face restoration. Returns ``(uint16, info)``."""
    out = sharpen(arr, amount=sharpen_amount)
    fb = "skipped"
    if face_restore:
        out, fb = restore_faces(out, fidelity=fidelity, backend=face_backend,
                                use_mock=use_mock)
    info = {"sharpen_amount": sharpen_amount, "face_backend": fb}
    log.info("deblur: unsharp %.2f, face-restore=%s", sharpen_amount, fb)
    return out, info
