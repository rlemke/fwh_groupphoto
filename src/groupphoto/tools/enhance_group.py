#!/usr/bin/env python3
"""enhance-group — enhance one posed group photo (deblur + glare + optional new bg).

Usage:
    enhance_group.py --image group.NEF --out-dir out/
    enhance_group.py --image group.jpg --out-dir out/ --background blur --out-format jpg
    enhance_group.py --image g.NEF --out-dir out/ --highlight-mode reconstruct --dcp
    enhance_group.py --image g.jpg --out-dir out/ --background image --bg-image beach.jpg

One enhanced photo per input (whole-frame; faces enhanced in place — no per-person
crops). stdout: JSON summary. stderr: logs. ``--use-mock`` runs the whole path with
no models/network.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _groupphoto_tools import pipeline  # noqa: E402

log = logging.getLogger("groupphoto.cli")


def add_pipeline_args(ap: argparse.ArgumentParser) -> None:
    """Shared pipeline knobs (also used by batch-group)."""
    g = ap.add_argument_group("glare / highlights")
    g.add_argument("--highlight-mode", choices=["clip", "blend", "reconstruct"],
                   default="clip", help="RAW highlight recovery (blown windows/sky)")
    g.add_argument("--no-clahe", action="store_true", help="disable CLAHE local-contrast")
    g.add_argument("--clahe-clip", type=float, default=2.0)
    g.add_argument("--dcp", action="store_true",
                   help="dark-channel-prior dehaze (strong veil removal; opt-in)")
    t = ap.add_argument_group("tone")
    t.add_argument("--no-dehaze", action="store_true")
    t.add_argument("--no-auto-brighten", action="store_true")
    t.add_argument("--brighten-target", type=float, default=120.0)
    d = ap.add_argument_group("deblur")
    d.add_argument("--sharpen", type=float, default=0.8, help="unsharp amount (0 disables)")
    d.add_argument("--no-face-restore", action="store_true")
    d.add_argument("--fidelity", type=float, default=0.7)
    d.add_argument("--face-backend", default="auto")
    b = ap.add_argument_group("background")
    b.add_argument("--background", choices=["none", "blur", "bokeh", "image", "color", "ai"],
                   default="none", help="prettier background (default: keep original)")
    b.add_argument("--bg-image", help="background image for --background image")
    b.add_argument("--bg-color", default="white", help="colour for --background color (#hex/name)")
    b.add_argument("--feather", type=float, default=3.0, help="matte edge feather (px)")
    b.add_argument("--matte-model", default="birefnet-general")
    o = ap.add_argument_group("detect / output")
    o.add_argument("--no-detect", action="store_true", help="skip person detection/metering")
    o.add_argument("--conf", type=float, default=0.25)
    o.add_argument("--model", default="yolo11x.pt")
    o.add_argument("--out-format", choices=["tiff", "jpg"], default="tiff")
    o.add_argument("--quality", type=int, default=100)
    o.add_argument("--use-mock", action="store_true")


def pipeline_kwargs(a: argparse.Namespace) -> dict:
    return dict(
        highlight_mode=a.highlight_mode, clahe=not a.no_clahe, clahe_clip=a.clahe_clip,
        dcp=a.dcp, dehaze=not a.no_dehaze, auto_brighten=not a.no_auto_brighten,
        brighten_target=a.brighten_target, sharpen_amount=a.sharpen,
        face_restore=not a.no_face_restore, fidelity=a.fidelity, face_backend=a.face_backend,
        background=a.background, bg_image=a.bg_image, bg_color=a.bg_color, feather=a.feather,
        matte_model=a.matte_model, detect_people=not a.no_detect, conf=a.conf,
        detect_model=a.model, out_format=a.out_format, quality=a.quality, use_mock=a.use_mock,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Enhance one posed group photo.")
    ap.add_argument("--image", required=True, help="input photo (RAW/JPEG/HEIC/…)")
    ap.add_argument("--out-dir", required=True, help="output directory")
    ap.add_argument("--log-level", default="INFO")
    add_pipeline_args(ap)
    a = ap.parse_args()

    logging.basicConfig(level=a.log_level.upper(), stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    summary = pipeline.enhance_group(a.image, a.out_dir, **pipeline_kwargs(a))
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
