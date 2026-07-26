# Deblur & Face Restoration

**Namespace:** (no facet of its own — a stage of `groupphoto.Enhance.EnhanceGroup`) ·
**Tools:** `src/groupphoto/tools/_groupphoto_tools/deblur.py`,
`_groupphoto_tools/enhance.py` (`unsharp16`, `restore_faces`) ·
**Tests:** `tests/test_deblur.py`

## Overview

The "blurriness" headline correction. Real-world group-photo blur is spatially
non-uniform and the perceptual win is almost entirely in the **faces**, so the v1 strategy
is *not* a global deblur net but: (1) a gentle whole-frame unsharp, then (2) optional
**face restoration** (GFPGAN/CodeFormer), which reconstructs soft faces far better than any
global deblur. A dedicated global-deblur model (NAFNet via `spandrel_extra_arches`, opt-in
`--deblur`) is phase 2 and not wired in.

## How it works

Everything stays `uint16` (H,W,3). `deblur.deblur(arr, sharpen_amount=0.8,
face_restore=True, fidelity=0.7, face_backend="auto")` returns `(uint16, info)`:

1. **`sharpen(arr, amount=0.8, radius=2.0)`** → `enhance.unsharp16` — a 16-bit unsharp mask
   (`cv2.GaussianBlur` at `sigmaX=radius`, `out = a + amount*(a - blur)`); `amount<=0`
   disables it. Always available (core deps only).
2. **`restore_faces(arr, fidelity=…, backend=…)`** — converts to 8-bit
   (`_to_pil8`, ÷257), calls `enhance.restore_faces`, and lifts the result back to 16-bit
   (`×257`). If the backend returns `"none"` (no lib/weights, or mock), the array is left
   **unchanged as true 16-bit**.

`enhance.restore_faces(img, fidelity, backend)` tries backends in order (`auto` →
`["gfpgan", "none"]`) and returns `(image, backend_used)`:

- **`_restore_gfpgan`** — `GFPGANer` (arch `clean`, `channel_multiplier=2`), multi-face
  (`only_center_face=False`, `paste_back=True`); our identity `fidelity` maps to GFPGAN's
  `weight`. It aliases `torchvision.transforms.functional_tensor` (removed in
  torchvision≥0.17) so basicsr imports on modern torch. Returns `None` → passthrough if the
  lib or `GFPGANv1.4.pth` weights are absent.
- **`_restore_codeformer`** — facexlib `FaceRestoreHelper` align/paste + the CodeFormer net
  via `spandrel_extra_arches`; `fidelity` → CodeFormer `weight`. Returns the input unchanged
  if no face is found. Selected only with `--face-backend codeformer`.

`fidelity` (0..1) trades identity-fidelity (high) vs restoration-strength (low). The `info`
dict records `sharpen_amount` and the actual `face_backend`.

## Fan-out

Not applicable — an in-memory stage of a single `EnhanceGroup`. Fleet parallelism is
per-photo (`EnhanceBatch`).

## Data & fields

Operates on the `uint16` H×W×3 array. Knobs: `--sharpen` (unsharp amount, 0 disables),
`--no-face-restore`, `--fidelity`, `--face-backend {auto,gfpgan,codeformer}`. Contributes
`face_backend` to the pipeline summary.

## External libraries / binaries

- **`opencv-python` + `numpy`** (core) — the unsharp mask; always runs.
- **`gfpgan`** + **`spandrel` / `spandrel_extra_arches`** (extra `[enhance]`) — face
  restoration; pulls `torch`, `basicsr`, `facexlib`. Needs weights
  (`~/.cache/groupphoto/weights/GFPGANv1.4.pth`, `codeformer.pth`; overridable via
  `FW_GROUPPHOTO_*_WEIGHTS`). **Reuses the same spandrel/gfpgan stack as `fwh_peloton`** —
  symlink that repo's weights dir to skip re-downloading.
- Device: `enhance._face_device()` defaults face detect/restore to **CPU**
  (retinaface/CodeFormer hit MPS op gaps); override with `FW_GROUPPHOTO_FACE_DEVICE`.

## Facets & workflows

None of its own — deblur is step 3 of `pipeline.enhance_group`, gated by
`sharpen_amount`/`face_restore`/`fidelity`/`face_backend` (CLI `--sharpen`/
`--no-face-restore`/`--fidelity`/`--face-backend`). The `EnhanceGroup` handler passes
`face_restore` through when present (default `False` at the handler layer,
`True` in the CLI defaults).

## Cache / output

No artifact of its own; folded into `<stem>_enhanced.{tif,jpg}`.

## Gotchas & notes

- **Enabling face restore forces the final stage to 8-bit precision** (the models are
  8-bit). The array type stays `uint16` but the last tonal precision is 8-bit. Leave it off
  for true 16-bit end-to-end; the banding-free tone work is already done upstream.
- **Graceful degradation is the contract** — a missing backend/weights → passthrough
  (`backend="none"`), never an error. Same contract as the cycling pipeline.
- **`enhance.py` also carries a Real-ESRGAN `upscale()` path** (`realesrgan-ncnn` binary →
  spandrel Real-ESRGAN → Lanczos, tiled inference). It is **reused from `fwh_peloton` and
  currently dormant** in the group pipeline — the whole-frame flow does no upscale. See
  [domain-and-cache](domain-and-cache.md) for the reused/dormant inventory.

## Related specs

- [enhance-pipeline](enhance-pipeline.md) — orchestration; also documents the tone stage
  (`auto_brighten16`/`dehaze16`) that shares `enhance.py`.
- [glare](glare.md) — the correction that runs before deblur.
- [detect](detect.md) — supplies the face/people boxes used for metering (not for cropping here).
