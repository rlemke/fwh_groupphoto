#!/usr/bin/env python3
"""replace-bg — swap only the background of a photo (matte the group, composite a new bg).

Usage:
    replace_bg.py --image group.jpg --out-dir out/ --background blur
    replace_bg.py --image group.jpg --out-dir out/ --background image --bg-image beach.jpg
    replace_bg.py --image group.jpg --out-dir out/ --background color --bg-color "#f0e8d8"

A focused tool for just the background step (no deblur/glare/tone). stdout: JSON;
stderr: logs. ``--use-mock`` uses a fixed matte (offline).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _groupphoto_tools import background as _bg  # noqa: E402
from _groupphoto_tools import images as _images  # noqa: E402

log = logging.getLogger("groupphoto.replacebg")


def main() -> int:
    ap = argparse.ArgumentParser(description="Replace only the background of a photo.")
    ap.add_argument("--image", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--background", choices=["blur", "bokeh", "image", "color"],
                    default="blur")
    ap.add_argument("--bg-image", help="background image for --background image")
    ap.add_argument("--bg-color", default="white")
    ap.add_argument("--feather", type=float, default=3.0)
    ap.add_argument("--matte-model", default="birefnet-general")
    ap.add_argument("--out-format", choices=["tiff", "jpg"], default="jpg")
    ap.add_argument("--quality", type=int, default=100)
    ap.add_argument("--use-mock", action="store_true")
    ap.add_argument("--log-level", default="INFO")
    a = ap.parse_args()

    logging.basicConfig(level=a.log_level.upper(), stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    src = Path(a.image)
    out_dir = Path(a.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    arr = _images.load_image16(src)
    arr, info = _bg.replace_background(
        arr, mode=a.background, bg_image=a.bg_image, color=a.bg_color,
        model=a.matte_model, feather=a.feather, use_mock=a.use_mock)

    ext = "tif" if a.out_format == "tiff" else "jpg"
    out_path = out_dir / f"{src.stem}_bg.{ext}"
    if a.out_format == "tiff":
        _images.save_tiff16(arr, out_path)
    else:
        a8 = np.clip(np.rint(arr.astype(np.float32) / 257.0), 0, 255).astype(np.uint8)
        _images.save_image(Image.fromarray(a8, "RGB"), out_path, quality=a.quality)

    summary = {"source": str(src), "output": str(out_path),
               "output_size": [int(arr.shape[1]), int(arr.shape[0])], **info}
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
