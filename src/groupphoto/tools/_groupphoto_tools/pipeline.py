"""End-to-end: one posed group photo → one enhanced photo.

    enhance_group(path) → load (16-bit) → glare correction → tone cleanup
                        → deblur/sharpen (+ face restore) → [optional background]
                        → write <stem>_enhanced.{tif,jpg}

Unlike the cycling pipeline there is NO per-person crop loop — the whole frame is the
unit and faces are enhanced in place. Pure orchestration over the ``_groupphoto_tools``
primitives; returns a JSON-serializable summary.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from _groupphoto_tools import background as _bg
from _groupphoto_tools import deblur as _deblur
from _groupphoto_tools import detect as _detect
from _groupphoto_tools import enhance as _enhance
from _groupphoto_tools import glare as _glare
from _groupphoto_tools import images as _images

log = logging.getLogger("groupphoto.pipeline")


def _to_pil8(arr: Any) -> Any:
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    a8 = np.clip(np.rint(arr.astype(np.float32) / 257.0), 0, 255).astype(np.uint8)
    return Image.fromarray(a8, "RGB")


def enhance_group(
    image_path: str | Path,
    out_dir: str | Path,
    *,
    # glare / highlights
    highlight_mode: str = "clip",         # clip | blend | reconstruct (RAW only)
    clahe: bool = True,
    clahe_clip: float = 2.0,
    dcp: bool = False,
    # tone cleanup
    dehaze: bool = True,
    auto_brighten: bool = True,
    brighten_target: float = 120.0,
    # deblur
    sharpen_amount: float = 0.8,
    face_restore: bool = True,
    fidelity: float = 0.7,
    face_backend: str = "auto",
    # background
    background: str = "none",             # none | blur | bokeh | image | color | ai
    bg_image: str | None = None,
    bg_color: str = "white",
    feather: float = 3.0,
    matte_model: str = "birefnet-general",
    # detection (exposure metering + headcount)
    detect_people: bool = True,
    conf: float = 0.25,
    detect_model: str = "yolo11x.pt",
    # output
    out_format: str = "tiff",             # tiff (16-bit) | jpg (8-bit)
    quality: int = 100,
    use_mock: bool = False,
) -> dict[str, Any]:
    """Enhance one group photo; writes a single output. Returns a summary dict."""
    import numpy as np  # noqa: PLC0415

    src = Path(image_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    arr = _images.load_image16(src, highlight_mode=highlight_mode)  # uint16 HxWx3
    h, w = int(arr.shape[0]), int(arr.shape[1])
    log.info("loaded %s (%dx%d), highlight_mode=%s", src.name, w, h, highlight_mode)

    # People: meter exposure on the group region (a backlit group is dark even when
    # the frame averages bright) + report a headcount.
    n_people = 0
    meter = None
    if detect_people:
        try:
            people = _detect.detect_people(_to_pil8(arr), conf=conf, model=detect_model,
                                           use_mock=use_mock)
            n_people = len(people)
            box = _detect.people_union_box(people, w, h, pad_frac=0.05)
            if box is not None:
                x1, y1, x2, y2 = (int(v) for v in box)
                meter = arr[y1:y2, x1:x2]
        except Exception as exc:  # noqa: BLE001 — detection is advisory, never fatal
            log.warning("person detection failed (%s) — metering on whole frame", exc)

    # 1) Glare: recoverable veil (CLAHE local-contrast + optional DCP dehaze).
    arr = _glare.correct_glare(arr, clahe=clahe, clahe_clip=clahe_clip, dcp=dcp)

    # 2) Tone cleanup (16-bit, banding-free): brighten the group toward target, then
    #    black/white-point dehaze.
    gamma = 1.0
    if auto_brighten:
        arr, gamma = _enhance.auto_brighten16(arr, meter=meter, target=brighten_target)
    if dehaze:
        arr = _enhance.dehaze16(arr)

    # 3) Deblur: whole-frame sharpen + optional face restoration (runs last so it
    #    sees the corrected tone; forces 8-bit precision when on).
    arr, dbinfo = _deblur.deblur(arr, sharpen_amount=sharpen_amount,
                                 face_restore=face_restore, fidelity=fidelity,
                                 face_backend=face_backend, use_mock=use_mock)

    # 4) Optional background replacement.
    arr, bginfo = _bg.replace_background(arr, mode=background, bg_image=bg_image,
                                         color=bg_color, model=matte_model,
                                         feather=feather, use_mock=use_mock)

    # 5) Save one output.
    ext = "tif" if out_format == "tiff" else "jpg"
    out_path = out / f"{src.stem}_enhanced.{ext}"
    if out_format == "tiff":
        _images.save_tiff16(arr, out_path)
    else:
        _images.save_image(_to_pil8(arr), out_path, quality=quality)

    summary = {
        "source": str(src),
        "source_size": [w, h],
        "n_people": n_people,
        "output": str(out_path),
        "output_size": [int(arr.shape[1]), int(arr.shape[0])],
        "out_format": out_format,
        "brighten_gamma": gamma,
        "face_backend": dbinfo["face_backend"],
        **bginfo,
    }
    log.info("done: %s → %s (%d people, brighten %.2f, bg=%s)", src.name,
             out_path.name, n_people, gamma, bginfo.get("background"))
    return summary
