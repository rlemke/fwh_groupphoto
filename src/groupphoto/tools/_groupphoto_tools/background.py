"""Background replacement for group photos — matte the group, composite a new bg.

Two steps:
  1. **Matting** — a foreground alpha for the whole group. Uses ``rembg`` with the
     BiRefNet model (best hair-level edges; semantic-foreground, so a multi-person
     group mattes in one pass), falling back to lighter rembg models, then bailing
     gracefully (no background change) if ``rembg`` isn't installed.
  2. **Composite** — blend the group over a new background: a blurred/bokeh version
     of the *same frame* (default, keeps colour + light consistent), a supplied
     image (cover-fit), or a solid colour. AI-generated backgrounds are phase 3.

16-bit (``uint16`` H,W,3) throughout. Matting runs on an 8-bit copy (the models are
8-bit) but the composite is done at 16-bit so tone fidelity survives.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from _groupphoto_tools import images as _images

log = logging.getLogger("groupphoto.background")

_SESSION_CACHE: dict[str, Any] = {}
# Ordered fallback: best hair alpha → lighter → tiny.
_MATTE_MODELS = ("birefnet-general", "isnet-general-use", "u2net")


def _to_pil8(arr: Any) -> Any:
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    a8 = np.clip(np.rint(arr.astype(np.float32) / 257.0), 0, 255).astype(np.uint8)
    return Image.fromarray(a8, "RGB")


def _session(model: str) -> Any:
    if model not in _SESSION_CACHE:
        from rembg import new_session  # noqa: PLC0415
        _SESSION_CACHE[model] = new_session(model)
        log.info("loaded rembg session: %s", model)
    return _SESSION_CACHE[model]


def matte(arr: Any, *, model: str = "birefnet-general", use_mock: bool = False) -> Any:
    """Foreground alpha (``uint8`` HxW, 0..255) for the group. ``None`` if matting is
    unavailable (rembg not installed / all models failed) so the caller skips the
    background change instead of erroring."""
    import numpy as np  # noqa: PLC0415

    h, w = int(arr.shape[0]), int(arr.shape[1])
    if use_mock:
        from _groupphoto_tools import groupphoto_mocks  # noqa: PLC0415
        return groupphoto_mocks.mock_matte(w, h)
    try:
        from rembg import remove  # noqa: PLC0415,F401
    except ImportError:
        log.warning("rembg not installed (pip install '.[matte]') — skipping background change")
        return None

    from rembg import remove  # noqa: PLC0415
    img8 = _to_pil8(arr)
    tried: list[str] = []
    for m in dict.fromkeys([model, *_MATTE_MODELS]):     # requested first, dedup
        tried.append(m)
        try:
            out = remove(img8, session=_session(m), only_mask=True, post_process_mask=True)
            alpha = np.asarray(out.convert("L"), dtype=np.uint8)
            log.info("matte via rembg model '%s' (%.1f%% foreground)",
                     m, 100.0 * (alpha > 127).mean())
            return alpha
        except Exception as exc:  # noqa: BLE001 — try the next model
            log.warning("rembg model '%s' failed: %s", m, exc)
    log.warning("all matte models failed (%s) — skipping background change", ", ".join(tried))
    return None


def composite(arr: Any, alpha: Any, *, mode: str = "blur", bg_image: str | None = None,
              feather: float = 3.0, blur_sigma: float | None = None,
              color: str = "white") -> Any:
    """Composite the foreground (``arr``, by ``alpha``) over a new background.

    mode: ``blur`` / ``bokeh`` (the same frame, progressively defocused — best
    default), ``image`` (``bg_image`` cover-fit), ``color`` (solid ``#hex``/name).
    ``feather`` softens the alpha edge (px). 16-bit in/out.
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    h, w = int(arr.shape[0]), int(arr.shape[1])
    fg = arr.astype(np.float32)

    if mode in ("blur", "bokeh"):
        sig = blur_sigma or (max(h, w) / (60.0 if mode == "blur" else 25.0))
        bg = cv2.GaussianBlur(fg, (0, 0), sigmaX=float(sig))
    elif mode == "image":
        if not bg_image:
            raise ValueError("background mode 'image' needs bg_image=")
        from PIL import Image, ImageOps  # noqa: PLC0415
        im = ImageOps.fit(_images.load_image(bg_image), (w, h), method=Image.LANCZOS)
        bg = np.asarray(im, dtype=np.float32) * 257.0
    elif mode == "color":
        from PIL import ImageColor  # noqa: PLC0415
        try:
            c = ImageColor.getrgb(color)
        except ValueError:
            c = (255, 255, 255)
        bg = np.empty_like(fg)
        bg[:] = np.asarray(c, dtype=np.float32) * 257.0
    else:
        raise ValueError(f"unknown background mode: {mode!r}")

    a = alpha.astype(np.float32)
    if feather > 0:
        a = cv2.GaussianBlur(a, (0, 0), sigmaX=float(feather))
    a = np.clip(a / 255.0, 0.0, 1.0)[..., None]
    out = fg * a + bg * (1.0 - a)
    log.info("composite: mode=%s feather=%.1f", mode, feather)
    return np.clip(out, 0, 65535).astype(np.uint16)


def replace_background(arr: Any, *, mode: str = "none", bg_image: str | None = None,
                       color: str = "white", model: str = "birefnet-general",
                       feather: float = 3.0, use_mock: bool = False,
                       ) -> tuple[Any, dict[str, Any]]:
    """Matte + composite. ``mode='none'`` is a no-op. Returns ``(uint16, info)``;
    if matting is unavailable the frame is returned unchanged with ``mode='none'``."""
    if mode == "none":
        return arr, {"background": "none"}
    if mode == "ai":                                     # phase 3 — degrade to blur
        log.warning("AI backgrounds are not implemented yet — using 'blur'")
        mode = "blur"
    alpha = matte(arr, model=model, use_mock=use_mock)
    if alpha is None:
        return arr, {"background": "none", "reason": "matte_unavailable"}
    out = composite(arr, alpha, mode=mode, bg_image=bg_image, color=color, feather=feather)
    info: dict[str, Any] = {"background": mode}
    if bg_image:
        info["bg_image"] = str(Path(bg_image).name)
    return out, info
