# Glare & Highlight Correction

**Namespace:** (no facet of its own — a stage of `groupphoto.Enhance.EnhanceGroup`) ·
**Tools:** `src/groupphoto/tools/_groupphoto_tools/glare.py`,
`_groupphoto_tools/images.py` (RAW highlight decode) ·
**Tests:** `tests/test_glare.py`

## Overview

One of the three headline corrections. Group photos suffer three physically-distinct
glare/highlight problems, and this feature is honest about which are recoverable:

1. **Veiling glare / sun haze** — a low-contrast bright veil. *Not lost data*, just reduced
   contrast, so genuinely fixable. Handled here (CLAHE + optional DCP dehaze).
2. **Blown windows / sky behind the group** — best recovered **at RAW decode** via LibRaw
   highlight modes (`images.load_image16(highlight_mode=…)`), which reconstruct from any
   channel that stayed below clipping. Fully-clipped pixels carry no data (only hideable by
   inpainting, phase 2). No pixels are invented here.
3. **Specular reflections** (skin shine, eyeglass glint) — inpaint removal is phase 2, and
   glasses that fully occlude the eyes are **intentionally left alone** (inpainting would
   fabricate eyes). Not done here.

## How it works

All ops are 16-bit (`uint16` H×W×3, float32 internally) to match the pipeline.
`correct_glare(arr, clahe=True, clahe_clip=2.0, dcp=False)` orchestrates two sub-steps:

- **`clahe_local(arr, clip=2.0, grid=8)`** (default on) — Contrast-Limited Adaptive
  Histogram Equalization on the **luminance** channel (`_LUMA = (0.299, 0.587, 0.114)`),
  re-applied to RGB as a per-pixel **gain** so colour is preserved. Lifts a veiling glare's
  local contrast without the global-clip risk of a full histogram stretch. Uses cv2's
  `createCLAHE`, which supports `uint16`.
- **`dehaze_dcp(arr, omega=0.85, tmin=0.2, patch=15, strength=…)`** (opt-in, `--dcp`) — the
  classic **Dark-Channel-Prior** single-image haze remover: estimate the atmospheric veil
  colour `A` (brightest 0.1% of the dark channel), the transmission map `t`, then pull the
  veil back out `J = (I - A)/t + A`. `strength` (default `0.7` via `correct_glare`
  `dcp_strength`) blends toward the original because DCP can over-darken faces at full
  strength.

The global black/white-point stretch and highlight recovery live **elsewhere** — the
pipeline's `enhance.dehaze16` (see [enhance-pipeline](enhance-pipeline.md) → tone) and the
`highlight_mode` argument to `load_image16` (see below), so this module is purely the
*recoverable-veil* path.

### RAW highlight recovery (the lever for blown windows)

`images.load_image16(path, highlight_mode=…)` maps three modes to LibRaw's
`highlight_mode` (RAW only): `clip` → 0 (hard clip, default), `blend` → 2 (gentle rolloff),
`reconstruct` → 5 (aggressive reconstruction). When actively recovering (blend/reconstruct)
it disables LibRaw auto-bright (`no_auto_bright=True`) so recovered highlights keep headroom
and don't immediately re-clip. **No effect on non-RAW inputs** — an already-clipped JPEG has
no sub-clipping channel data to reconstruct from.

## Fan-out

Not applicable — glare correction is an in-memory array op inside a single `EnhanceGroup`.
Fleet parallelism is at the photo level (`EnhanceBatch`); see [enhance-pipeline](enhance-pipeline.md).

## Data & fields

Works on the `uint16` H×W×3 array in place. Knobs: `--no-clahe`, `--clahe-clip` (default
2.0), `--dcp`, `--highlight-mode {clip,blend,reconstruct}`. No separate output/summary
fields — its effect is folded into the enhanced photo.

## External libraries / binaries

- **`opencv-python`** (core) — `createCLAHE`, `erode`/`getStructuringElement` (dark
  channel), `blur` (transmission refine).
- **`numpy`** (core) — the luminance/gain and DCP math.
- **`rawpy` / LibRaw** (extra `[raw]`, a **binary**-backed pip dep) — the highlight-mode
  RAW decode; without it RAW files raise a clear install error and highlight recovery is
  unavailable, but JPEG/HEIC glare correction still runs on the core deps.

## Facets & workflows

None of its own — glare is invoked as step 1 of `pipeline.enhance_group`, gated by the
`clahe`/`clahe_clip`/`dcp` kwargs (CLI `--no-clahe`/`--clahe-clip`/`--dcp`) and, for RAW
highlights, the `highlight_mode` kwarg carried through `EnhanceGroup(highlight_mode=…)`.

## Cache / output

No artifact of its own; the correction is baked into `<stem>_enhanced.{tif,jpg}`. All ops
are lossless-precision `uint16`.

## Gotchas & notes

- **Blown highlights are a RAW-decode decision, not a pixel op.** Reach for
  `--highlight-mode reconstruct` on RAW *before* expecting `--dcp` to save blown windows —
  fully-clipped pixels are gone.
- **DCP can over-darken faces** — hence the `strength=0.7` blend; it's opt-in for that reason.
- **Occluded-eye eyeglass glare is deliberately not touched** — a sensitivity/honesty choice.

## Related specs

- [enhance-pipeline](enhance-pipeline.md) — the orchestration and the tone-cleanup stage
  (`dehaze16`) that finishes the global tonal fix.
- [image-io](image-io.md) — `load_image16` and the `highlight_mode` RAW decode.
