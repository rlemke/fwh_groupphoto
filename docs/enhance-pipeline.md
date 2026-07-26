# Enhance Pipeline (whole-frame)

**Namespace:** `groupphoto.Enhance` · `groupphoto.workflows` ·
**FFL:** `src/groupphoto/ffl/groupphoto.ffl` ·
**Handler:** `src/groupphoto/handlers/enhance/enhance_handlers.py` ·
**Tools:** `src/groupphoto/tools/_groupphoto_tools/pipeline.py` (orchestration),
`_groupphoto_tools/enhance.py` (tone) ·
**CLI:** `src/groupphoto/tools/enhance_group.py`, `batch_group.py` ·
**Tests:** `tests/test_pipeline_mock.py`, `tests/test_ffl_domain.py`

## Overview

This is the flagship feature: take **one posed group photo** and return **one enhanced
photo** (the whole frame, faces fixed in place), unlike the per-rider cycling pipeline
`fwh_groupphoto` reuses code from. It answers "clean up this family/team/reunion shot":
correct veiling glare and blown highlights, lift a backlit group's exposure, sharpen and
restore soft faces, and optionally swap the background. `pipeline.enhance_group()` is the
orchestrator; `handle_enhance_group` (facet `groupphoto.Enhance.EnhanceGroup`) and the
`enhance-group` / `batch-group` CLIs are its three front doors.

## How it works

`enhance_group(image_path, out_dir, …)` in `pipeline.py` is pure orchestration over the
`_groupphoto_tools` primitives — **there is no per-person crop loop** (contrast the
cycling pipeline); the whole frame is the unit. Data shape:
`RAW/JPEG/HEIC → uint16 HxWx3 working array → <stem>_enhanced.{tif,jpg}`.

1. **Load 16-bit** — `images.load_image16(src, highlight_mode=…)` decodes to a `uint16`
   H×W×3 array. Camera RAW is decoded straight to 16-bit (`output_bps=16`) so the full
   ~14-bit sensor range survives the tonal math banding-free (see [image-io](image-io.md)).
2. **Detect & meter (advisory)** — if `detect_people`, `detect.detect_people` runs YOLO,
   `people_union_box` gives the "where the group is" box, and the array is sliced to it as
   the **exposure meter** — a backlit group is dark even when the frame averages bright.
   Detection failure is caught and logged; it never aborts the enhance (see [detect](detect.md)).
3. **Glare** — `glare.correct_glare(arr, clahe=, clahe_clip=, dcp=)`: CLAHE local-contrast
   (default on) + optional dark-channel-prior dehaze (see [glare](glare.md)).
4. **Tone cleanup** (16-bit, banding-free, in `enhance.py`) — `auto_brighten16(arr,
   meter=…, target=120)` gamma-lifts the metered group toward a target mean luminance
   (highlights preserved, capped at `max_gamma=2.4`), then `dehaze16(arr)` stretches the
   black/white points per-image percentiles + a mild contrast/colour lift. These are the
   float32-on-`uint16` re-implementations of the 8-bit `auto_brighten`/`dehaze` so a heavy
   stretch stays banding-free.
5. **Deblur** — `deblur.deblur(arr, sharpen_amount=, face_restore=)`: whole-frame unsharp
   + optional GFPGAN/CodeFormer face restoration, run last so it sees corrected tone (see
   [deblur](deblur.md)).
6. **Background (optional)** — `background.replace_background(arr, mode=…)`: matte the
   group and composite onto blur/bokeh/image/color; `mode="none"` (default) is a no-op
   (see [background](background.md)).
7. **Save one output** — 16-bit lossless TIFF (`save_tiff16`) or 8-bit JPEG
   (`save_image`), `out_dir/<stem>_enhanced.{tif,jpg}`.

Returns a JSON summary: `source`, `source_size`, `n_people`, `output`, `output_size`,
`out_format`, `brighten_gamma`, `face_backend`, plus the background `info` keys.

## Fan-out

- **`EnhanceOne(image_path, out_dir, background)`** — one photo → one output; a single
  `EnhanceGroup` step. No fan-out.
- **`EnhanceBatch(paths, out_dir, background)`** — `andThen foreach path in $.paths`, one
  `EnhanceGroup` task **per photo across the fleet**; `paths` typically comes from
  `Ingest.ListImages(in_dir)`. This is the fleet-parallel batch path — each photo is
  independent and heavy (models + a large RAW), so per-photo fan-out reduces wall-clock.
- The `batch-group` CLI is the **single-process** counterpart: it loops a directory in one
  process, **reusing loaded models across photos** and writing a running `manifest.json`
  (`--resume` skips sources already recorded). Fleet fan-out (`EnhanceBatch`) trades model
  re-load per task for parallelism; the CLI trades parallelism for model reuse.

## Data & fields

- **Inputs:** camera RAW (`.nef/.cr2/.arw/.dng/…`), `.jpg/.jpeg/.png/.webp/.bmp/.tif/.heic/.heif`.
- **Knobs** (CLI flags → `pipeline_kwargs`): `--highlight-mode {clip,blend,reconstruct}`,
  `--no-clahe`/`--clahe-clip`, `--dcp`, `--no-dehaze`, `--no-auto-brighten`/`--brighten-target`,
  `--sharpen`, `--no-face-restore`/`--fidelity`/`--face-backend`,
  `--background {none,blur,bokeh,image,color,ai}`/`--bg-image`/`--bg-color`/`--feather`/`--matte-model`,
  `--no-detect`/`--conf`/`--model`, `--out-format {tiff,jpg}`/`--quality`, `--use-mock`.
- **Summary fields:** `n_people` (headcount), `brighten_gamma` (1.0 = no lift needed),
  `face_backend` (`gfpgan`/`codeformer`/`none`/`skipped`), `background` (`none`/`blur`/…).

## External libraries / binaries

Orchestration itself is pure Python. It pulls in, lazily and per-stage: **`numpy`**,
**`opencv-python`**, **`Pillow`**, **`tifffile`** (all core); and the optional extras that
each stage degrades without — `ultralytics`/`torch` (`[detect]`), `gfpgan`/`spandrel`
(`[enhance]`), `rembg`/`onnxruntime` (`[matte]`), `rawpy` (`[raw]`). The pipeline is
designed to run on the **core deps alone** (glare/tone/sharpen), with face-restore →
passthrough and background → skipped when their extras are absent.

## Facets & workflows

| Facet / Workflow | Kind | Effect | Purpose (from FFL docstring) |
|---|---|---|---|
| `Enhance.EnhanceGroup(image_path, out_dir, background="none", out_format="tiff", highlight_mode="clip")` → `(output, n_people)` | event | io | Enhance one posed group photo in place — glare/highlight + deblur + tone + optional bg swap. |
| `Enhance.ReplaceBackground(...)` → `(output)` | event | io | Background-only; documented in [background](background.md). |
| `workflows.EnhanceOne(image_path, out_dir, background)` → `(output)` | workflow | — | One photo → one enhanced photo. |
| `workflows.EnhanceBatch(paths, out_dir, background)` → `(count)` | workflow | — | Fan out per photo (`foreach path in $.paths`). |

Schema `groupphoto.EnhanceResult { output: String, n_people: Long }` is declared in the
top-level `groupphoto` namespace (the facet returns the same shape inline). The handler
also honours params not in the FFL signature (`face_restore`, `use_mock`) when passed.

## Cache / output

Writes exactly one file per input to `out_dir` — `<stem>_enhanced.tif` (16-bit deflate
TIFF, archival master) or `<stem>_enhanced.jpg` (8-bit). `batch-group` additionally writes
`<out>/manifest.json` (processed/total/ok/failed/people + per-photo records). Outputs are
written to the local `out_dir` path; the handler does **not** currently route through the
`_groupphoto_tools/storage.py` S3/MinIO backend or the sidecar cache (see
[domain-and-cache](domain-and-cache.md)).

## Gotchas & notes

- **Face restore trades final precision to 8-bit.** The models are 8-bit, so when
  `face_restore` is on the array round-trips through 8-bit for the last stage; the
  banding-free 16-bit tone work has already happened upstream. Leave it off for true
  16-bit end-to-end.
- **Meter on the group, not the frame.** Auto-brighten meters on the people-union box; a
  backlit group is under-exposed even when the frame's average looks fine. If detection is
  unavailable it falls back to whole-frame metering (a milder, sometimes wrong lift).
- **`--use-mock` runs the whole path with no models/network** — deterministic 4 people +
  a central matte (`groupphoto_mocks`), which is how the offline test suite exercises it.
- **`background="ai"` is a phase-3 stub** — it warns and degrades to `blur`.

## Related specs

- [glare](glare.md), [deblur](deblur.md), [background](background.md), [detect](detect.md)
  — the four correction stages this orchestrates.
- [image-io](image-io.md) — the 16-bit load/save + RAW/HEIC handling underneath.
- [conversion](conversion.md) — the ingest side (`ListImages` feeds `EnhanceBatch`).
- [domain-and-cache](domain-and-cache.md) — how these facets are registered and run on the fleet.
