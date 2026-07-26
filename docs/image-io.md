# Image I/O (16-bit load / save, RAW / HEIC / TIFF)

**Namespace:** (foundational — no facet of its own) ·
**Tools:** `src/groupphoto/tools/_groupphoto_tools/images.py` ·
**CLI:** `src/groupphoto/tools/tiffs_to_jpegs.py` (the derive-JPEG step) ·
**Tests:** `tests/test_tiffs_to_jpegs.py` (+ used throughout the other suites)

## Overview

The thin, shared I/O layer under **every** other feature: decode any supported input to a
16-bit working array, write lossless 16-bit TIFF masters, and downconvert to 8-bit JPEGs
for sharing. Getting this right — decoding RAW straight to 16-bit and keeping the pipeline
`uint16` — is what makes the heavy tone stretches (glare/brighten/dehaze) banding-free.

## How it works

- **`load_image(path)`** → an RGB `PIL.Image`, EXIF-orientation applied
  (`ImageOps.exif_transpose`). RAW extensions route to `_load_raw` (rawpy `postprocess`,
  camera WB, 8-bit); `.heic/.heif` open transparently after a one-time
  `pillow_heif.register_heif_opener()` (`_ensure_heif`, no-op if pillow-heif absent).
- **`load_image16(path, highlight_mode="clip")`** → `uint16` H×W×3, the pipeline's working
  form:
  - **16-bit TIFF** → read via `tifffile` at real depth; 8-bit → lifted `×257`.
  - **RAW** → `rawpy.postprocess(output_bps=16)` so the full ~14-bit sensor range survives;
    `highlight_mode` maps to LibRaw modes `clip=0 / blend=2 / reconstruct=5` (auto-bright
    disabled when recovering) — the lever for blown windows/sky (see [glare](glare.md)).
  - **other 8-bit** (JPEG/PNG/HEIC) → `load_image` then lifted `×257` (no real >8-bit data).
- **`save_tiff16(arr, path, dpi=)`** → lossless **deflate** TIFF, `photometric="rgb"`. The
  archival, maximum-fidelity output (no DCT/8-bit quantization).
- **`tiff_to_image8(path)`** → 8-bit RGB `PIL.Image` (16-bit scaled 65535→255 ÷257,
  grayscale expanded, alpha dropped) — the JPEG-derive downconvert.
- **`save_image(img, path, quality=92, dpi=)`** → JPEG by extension (with an `optimize` +
  `MAXBLOCK` guard against libjpeg scanline-buffer overflow on high-entropy images; falls
  back to an unoptimized encode on `OSError`), else PNG-ish; optional print-DPI tag.
- Helpers: `size`, `fit_to_size` (aspect-preserving pad, `blur` fill option), `RAW_EXTS`
  (the 15-extension camera-RAW set).

`tiffs_to_jpegs.py` (`convert_dir`) is the standalone derive step: for a directory of
16-bit `.tif` masters it writes an 8-bit `.jpg` copy of each into a *different* directory
(same stem) via `tiff_to_image8` + `save_image` — no re-detection, no re-enhancement, so
it's fast and idempotent (`--overwrite` forces; default skips existing).

## Fan-out

Not applicable — a library layer. `tiffs-to-jpegs` is a single-process directory loop (no
workflow/facet); it is not wired to the fleet.

## Data & fields

- **`RAW_EXTS`:** `.nef .nrw .cr2 .cr3 .crw .arw .srf .sr2 .dng .raf .orf .rw2 .pef .srw`.
- **Working array:** `uint16` H×W×3 throughout the pipeline.
- **`tiffs-to-jpegs` summary:** `total`, `converted`, `skipped`, `failed`, `outputs`,
  `elapsed_seconds`.

## External libraries / binaries

- **`Pillow`** (core) — load/save, EXIF transpose, JPEG encode; imported lazily behind a
  clear error (`_pil`).
- **`tifffile`** (core) — 16-bit TIFF read/write.
- **`numpy`** (core) — array conversions.
- **`pillow-heif`** (core) — `.heic/.heif` decode (graceful no-op if absent).
- **`rawpy` / LibRaw** (extra `[raw]`, **binary**-backed) — camera RAW decode + highlight
  recovery; RAW inputs raise a clear "install `.[raw]`" error when it's missing.

## Facets & workflows

None — this is the shared substrate. (`tiffs-to-jpegs` is a CLI-only derive step with no
FFL facet; the RAW→TIFF facet is `Ingest.ConvertRaw`, documented in [conversion](conversion.md).)

## Cache / output

`save_tiff16` → 16-bit deflate `.tif` (archival master); `save_image` → 8-bit `.jpg`
(shareable). Both write to the caller's path; the S3/MinIO `storage.py` backend exists but
is not wired into these functions (see [domain-and-cache](domain-and-cache.md)).

## Gotchas & notes

- **8-bit inputs have no 16-bit data** — lifting JPEG/PNG ×257 gives a uniform pipeline
  type, not extra tonal range; the banding-free benefit is real only for RAW/16-bit-TIFF.
- **JPEG `optimize` can overflow libjpeg** on high-entropy images → the `MAXBLOCK` bump +
  unoptimized-encode fallback in `save_image` is load-bearing; don't remove it.
- **`tiff_to_image8` drops alpha and extra channels** and expects RGB(-ish) TIFFs — it's the
  derive step, not a general TIFF reader.
- **DPI is a tag, not a resample** — `save_image(dpi=)` sets print resolution metadata only.

## Related specs

- [conversion](conversion.md) — builds on `load_image16`/`save_tiff16` for the bulk engine.
- [glare](glare.md) — the `highlight_mode` RAW decode lives here.
- [enhance-pipeline](enhance-pipeline.md) — load/save bracket the whole enhance.
