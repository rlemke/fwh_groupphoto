# Background Replacement

**Namespace:** `groupphoto.Enhance` (facet `ReplaceBackground`; also a stage of
`EnhanceGroup`) · **FFL:** `src/groupphoto/ffl/groupphoto.ffl` ·
**Handler:** `src/groupphoto/handlers/enhance/enhance_handlers.py` (`handle_replace_background`) ·
**Tools:** `src/groupphoto/tools/_groupphoto_tools/background.py` ·
**CLI:** `src/groupphoto/tools/replace_bg.py` · **Tests:** `tests/test_background.py`

## Overview

The "prettier background" headline correction. Matte the whole group out of the frame and
composite them over a new background — a defocused version of the *same* frame (keeps
colour + light consistent), a supplied image, or a solid colour. Available both as a
**stage** of the full enhance (`--background`) and as a **focused, standalone** operation
(`ReplaceBackground` facet / `replace-bg` CLI) that does only matte + composite, no
deblur/glare/tone.

## How it works

Two steps, 16-bit (`uint16` H,W,3) throughout; matting runs on an 8-bit copy (models are
8-bit) but the composite is 16-bit so tone fidelity survives.

1. **Matte — `matte(arr, model="birefnet-general")`** — foreground alpha (`uint8` H×W,
   0..255) for the whole group via **rembg**. `birefnet-general` gives the best hair-level
   edges and is semantic-foreground, so a multi-person group mattes in **one pass**; it
   falls through an ordered fallback `("birefnet-general", "isnet-general-use", "u2net")`
   (requested model first, deduped), each session cached in `_SESSION_CACHE`. Returns
   `None` — caller **skips** the background change instead of erroring — if rembg isn't
   installed or every model fails. `use_mock=True` returns a deterministic central-band
   matte (`groupphoto_mocks.mock_matte`).
2. **Composite — `composite(arr, alpha, mode=…, feather=3.0)`**:
   - `blur` / `bokeh` — the same frame gaussian-blurred (`sigma = max(h,w)/60` for blur,
     `/25` for bokeh — a stronger defocus).
   - `image` — `bg_image` cover-fit (`ImageOps.fit`, LANCZOS); raises if `bg_image` is missing.
   - `color` — a solid `#hex`/name via `ImageColor.getrgb` (falls back to white on a bad value).
   - `feather` gaussian-softens the alpha edge; final blend `fg*a + bg*(1-a)`.

`replace_background(arr, mode="none", …)` is the entry point: `mode="none"` is a no-op;
`mode="ai"` warns (phase 3) and degrades to `blur`; a `None` matte returns the frame
unchanged with `{"background": "none", "reason": "matte_unavailable"}`.

## Fan-out

Not applicable at the operation level. As a stage it inherits `EnhanceBatch`'s per-photo
fan-out; the standalone `ReplaceBackground` facet is a single-task per photo (no batch
workflow declared for it).

## Data & fields

Knobs: `--background {none,blur,bokeh,image,color,ai}` (or the facet `mode`), `--bg-image`,
`--bg-color`, `--feather`, `--matte-model`. The returned `info` carries `background` (the
mode actually used) and, for `image`, `bg_image` (basename). The standalone CLI/handler
default to a `.jpg` output; the pipeline stage keeps the pipeline's `--out-format`.

## External libraries / binaries

- **`rembg`** + **`onnxruntime`** (extra `[matte]`) — the matting models. **Optional and
  lazy-imported**: absent → the background change is skipped (logged), the rest of the
  enhance still runs.
- **`opencv-python`** (core) — gaussian blur, the composite math.
- **`Pillow` / `numpy`** (core) — `bg_image` cover-fit, colour parsing, 8-bit round-trip.
- Model weights download to rembg's own cache on first use.

## Facets & workflows

| Facet | Kind | Effect | Purpose (from FFL docstring) |
|---|---|---|---|
| `Enhance.ReplaceBackground(image_path, out_dir, mode="blur", bg_image="")` → `(output)` | event | io | Replace only the background: matte the group and composite onto a blurred version of the same frame, or a supplied image. |

`handle_replace_background` loads 16-bit, calls `replace_background`, writes
`<stem>_bg.jpg` (8-bit). The `replace-bg` CLI additionally supports `color`/`bokeh` modes
and `--out-format tiff`. As a stage of `EnhanceGroup`, background is the last transform
before save.

## Cache / output

Standalone: `out_dir/<stem>_bg.{jpg,tif}`. As a stage: folded into `<stem>_enhanced.*`.
Local `out_dir` (no storage-backend routing at the handler layer — see
[domain-and-cache](domain-and-cache.md)).

## Gotchas & notes

- **A multi-person group mattes in one pass** — BiRefNet is semantic-foreground, so there's
  no per-person loop; that's the whole reason to use it over a portrait matter.
- **Matte-unavailable is a graceful skip, not a failure** — a photo comes back with the
  original background and `reason: matte_unavailable` rather than erroring.
- **`ai` mode is a phase-3 stub** — it degrades to `blur` today.
- **The reused `crop.cutout()` per-object blur/bokeh/replace path** (from `fwh_peloton`) is
  a *different, dormant* code path — the group pipeline mattes the whole frame via
  `background.py`, not per-person cutouts. See [domain-and-cache](domain-and-cache.md).

## Related specs

- [enhance-pipeline](enhance-pipeline.md) — background as the final enhance stage.
- [detect](detect.md) — not required for matting (rembg is semantic), but shares the
  "group region" concept.
- [domain-and-cache](domain-and-cache.md) — dormant per-object cutout code.
