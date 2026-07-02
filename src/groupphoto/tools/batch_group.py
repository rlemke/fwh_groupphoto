#!/usr/bin/env python3
"""batch-group — enhance a whole directory of group photos.

Usage:
    batch_group.py --in-dir photos/ --out-dir out/
    batch_group.py --in-dir photos/ --out-dir out/ --background blur --out-format tiff --resume

Processes every image in --in-dir (reusing loaded models across photos), writes one
enhanced output per input plus a running <out>/manifest.json, and continues past
per-photo errors. Same pipeline knobs as enhance-group. stdout: JSON summary; stderr: logs.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _groupphoto_tools import images, pipeline  # noqa: E402
from enhance_group import add_pipeline_args, pipeline_kwargs  # noqa: E402

_EXTS = ({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
         | images.RAW_EXTS)
log = logging.getLogger("groupphoto.batch")


def main() -> int:
    ap = argparse.ArgumentParser(description="Enhance a directory of group photos.")
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--limit", type=int, default=0, help="process at most N photos (0 = all)")
    ap.add_argument("--resume", action="store_true",
                    help="skip sources already recorded in <out>/manifest.json")
    ap.add_argument("--log-level", default="INFO")
    add_pipeline_args(ap)
    a = ap.parse_args()

    logging.basicConfig(level=a.log_level.upper(), stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    kw = pipeline_kwargs(a)

    in_dir, out_dir = Path(a.in_dir).expanduser(), Path(a.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    photos = sorted(p for p in in_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in _EXTS)
    if a.limit:
        photos = photos[:a.limit]
    if not photos:
        log.error("no images found in %s", in_dir)
        return 1

    manifest: list[dict] = []
    done: set[str] = set()
    n_ok = n_fail = n_people = 0
    mf = out_dir / "manifest.json"
    if a.resume and mf.exists():
        try:
            prior = json.loads(mf.read_text())
            manifest = prior.get("photos", [])
            for e in manifest:
                done.add(e["source"])
                if "error" in e:
                    n_fail += 1
                else:
                    n_ok += 1
                    n_people += e.get("n_people", 0)
            log.info("resume: %d source(s) already in manifest — skipping", len(done))
        except Exception as exc:  # noqa: BLE001
            log.warning("resume: could not read manifest (%s) — starting fresh", exc)
    log.info("batch: %d photo(s) from %s → %s (%d remaining)", len(photos), in_dir,
             out_dir, len([p for p in photos if str(p) not in done]))

    for i, f in enumerate(photos, 1):
        if str(f) in done:
            continue
        t0 = time.time()
        try:
            s = pipeline.enhance_group(f, out_dir, **kw)
            dt = time.time() - t0
            n_ok += 1
            n_people += s["n_people"]
            manifest.append({"source": str(f), "output": s["output"],
                             "n_people": s["n_people"], "background": s.get("background"),
                             "seconds": round(dt, 1)})
            log.info("[%d/%d] %s → %s (%d people) in %.1fs", i, len(photos), f.name,
                     Path(s["output"]).name, s["n_people"], dt)
        except Exception as exc:  # noqa: BLE001 — keep going across bad photos
            n_fail += 1
            manifest.append({"source": str(f), "error": str(exc)})
            log.error("[%d/%d] %s FAILED: %s", i, len(photos), f.name, exc)
        (out_dir / "manifest.json").write_text(json.dumps(
            {"processed": i, "total": len(photos), "ok": n_ok, "failed": n_fail,
             "people": n_people, "photos": manifest}, indent=2))

    summary = {"total": len(photos), "ok": n_ok, "failed": n_fail, "people": n_people,
               "out_dir": str(out_dir)}
    log.info("DONE: %d photos (%d ok, %d failed), %d people", len(photos), n_ok, n_fail,
             n_people)
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
