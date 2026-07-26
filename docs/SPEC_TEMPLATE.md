<!-- SPEC TEMPLATE — every docs/<feature>.md follows this shape so the set reads
consistently. Delete this comment in real specs. Keep sections in this order;
omit a section only if it genuinely does not apply (say so in one line rather
than dropping the heading silently). Ground every claim in the actual FFL
docstrings / handler code / tools — do not invent behaviour. -->

# <Feature Name>

**Namespace(s):** `groupphoto.<ns>` · **FFL:** `src/groupphoto/ffl/groupphoto.ffl` ·
**Handlers:** `src/groupphoto/handlers/<dir>/*.py` ·
**Tools:** `src/groupphoto/tools/_groupphoto_tools/<...>.py` · **CLI:** `src/groupphoto/tools/<...>.py`

## Overview
One or two paragraphs: what this feature is for, the request it answers, and where it
sits in the pipeline (load → glare → tone → deblur → background → save, or
ingest/convert → enhance).

## How it works
The algorithm / data flow, step by step. Name the concrete functions and the shape of
the data at each (RAW/JPEG/HEIC → uint16 HxWx3 → corrected array → `<stem>_enhanced.tif`,
etc.). Note the bit depth (16-bit `uint16` working image vs 8-bit output) and where a
model runs vs where a pure-numpy/OpenCV path runs.

## Fan-out
Does it fan out across the fleet? If yes: what is the fan-out unit (per-photo /
per-file), which facet drives it (a `foreach` over what list — `EnhanceBatch` /
`ConvertBatch` over `paths`), and why it reduces wall-clock. If it is single-task
or single-step-multi-threaded (`ConvertDir`/`CopyDir`), say so and why.

## Data & fields
What data the feature reads and writes — inputs (camera RAW `.nef/.cr2/.arw/.dng/…`,
`.jpg/.heic/.tif`), the working array, and the emitted fields (the JSON summary keys,
e.g. `output`, `n_people`, `converted`/`skipped`/`failed`, `background`,
`brighten_gamma`, `face_backend`). Name any tunable knobs (CLAHE `clip`,
`highlight_mode`, matte `model`, `--workers`). (For a filter/geo domain this would be
"Filtering & attributes"; this domain is pixel/format work, so it is "Data & fields".)

## External libraries / binaries
Every non-stdlib dependency this feature relies on and what for — e.g. `opencv-python`
(CLAHE, gaussian blur, resize, dehaze), `numpy`, `Pillow`, `tifffile` (16-bit TIFF),
`rawpy`/LibRaw (RAW decode — a **binary**-backed pip dep), `pillow-heif` (HEIC),
`rembg` + `onnxruntime` (matting), `gfpgan`/`spandrel`/`spandrel_extra_arches` (face
restore), `ultralytics`/`torch` (detection). Distinguish an **optional extra**
(lazy-imported, degrades gracefully) from a **core** dep, and a **binary** dep from a
**pip** one.

## Facets & workflows
The key event facets and workflows, with signatures and a one-line purpose taken from
the FFL `/** … */` docstrings. Mark event facets (need a handler) vs pure facets, and
note `Effect`/`Cost` mixins where present (every facet here declares
`with Effect(kind = "io")`).

## Cache / output
The output artifact(s) and format (16-bit lossless TIFF / 8-bit JPEG / a running
`manifest.json`). Where they go (local `out_dir` vs, in principle, MinIO/S3 via
`_groupphoto_tools/storage.py`). Note the graceful-degradation contract (which steps
are skipped when an extra is absent).

## Gotchas & notes
Known pitfalls, precision trade-offs (e.g. face restore forces 8-bit), what is honestly
*not* recoverable (fully-clipped highlights, occluded-eye glasses glare), dormant/
reused-from-`fwh_peloton` code, and phase-2/3 stubs.

## Related specs
Links to the specs this feature composes with or depends on.
