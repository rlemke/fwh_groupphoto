"""Handlers for groupphoto.Enhance — whole-photo enhance + background replace."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from groupphoto.handlers.shared import groupphoto_utils as U

NAMESPACE = "groupphoto.Enhance"


def handle_enhance_group(params: dict[str, Any]) -> dict[str, Any]:
    s = U.pipeline.enhance_group(
        params["image_path"], params["out_dir"],
        background=params.get("background", "none"),
        out_format=params.get("out_format", "tiff"),
        highlight_mode=params.get("highlight_mode", "clip"),
        face_restore=params.get("face_restore", False),
        use_mock=params.get("use_mock", False),
    )
    return {"output": s["output"], "n_people": s["n_people"]}


def handle_replace_background(params: dict[str, Any]) -> dict[str, Any]:
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    src = Path(params["image_path"]).expanduser()
    out_dir = Path(params["out_dir"]).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    arr = U.images.load_image16(src)
    arr, info = U.background.replace_background(
        arr, mode=params.get("mode", "blur"), bg_image=(params.get("bg_image") or None),
        use_mock=params.get("use_mock", False))
    out = out_dir / f"{src.stem}_bg.jpg"
    a8 = np.clip(np.rint(arr.astype(np.float32) / 257.0), 0, 255).astype(np.uint8)
    U.images.save_image(Image.fromarray(a8, "RGB"), out, quality=100)
    return {"output": str(out)}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.EnhanceGroup": handle_enhance_group,
    f"{NAMESPACE}.ReplaceBackground": handle_replace_background,
}


def handle(payload: dict) -> dict:
    return _DISPATCH[payload["_facet_name"]](payload)


def register_handlers(runner) -> None:
    for facet_name in _DISPATCH:
        runner.register_handler(facet_name=facet_name, module_uri=__name__, entrypoint="handle")
