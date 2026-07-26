# Conversion & Copy Engine (ingest)

**Namespace:** `groupphoto.Ingest` · `groupphoto.workflows` ·
**FFL:** `src/groupphoto/ffl/groupphoto.ffl` ·
**Handler:** `src/groupphoto/handlers/ingest/ingest_handlers.py` ·
**Tools:** `src/groupphoto/tools/convert_photos.py`,
`_groupphoto_tools/copytree.py` ·
**CLI:** `convert_photos.py` (alias `nef_to_tif.py`), `copy_tree.py` ·
**Tests:** `tests/test_nef_to_tif.py`, `tests/test_copytree.py`, `tests/test_ffl_domain.py`

## Overview

The ingest / bulk-conversion side of the domain — independent of the enhance pipeline. It
converts **RAW/TIFF/JPEG/PNG/HEIC → TIFF or JPEG** at any resolution, and mirror-copies
directory trees, both with an **adaptive multi-threaded** engine that sizes its worker pool
to the free CPUs. This is what turns a shoot's worth of 45 MP `.NEF` files into lossless
16-bit TIFF masters (or shareable JPEGs), and what stages/backs up trees between volumes.

## How it works

**Convert** (`convert_photos.py`): every input is decoded to a 16-bit working image
(`images.load_image16`), optionally resized (`_resize_arr`, cv2 `INTER_AREA` downscale /
`INTER_LANCZOS4` upscale), then saved — TIFF via `save_tiff16` (lossless 16-bit) or JPEG
via an 8-bit downconvert (÷257). Helpers: `parse_resize` (`N` long-edge · `WxH` fit-box ·
`50%`/`0.5` scale), `parse_from` (`raw` · `any` · an extension list). Three scopes:
`convert_one` (a file), `convert_dir` (one level), `convert_tree` (recursive, **mirroring
the input tree** into `out_dir`, writing `_convert_manifest.json`).

**Adaptive parallelism** (`_convert_many` + `_resolve_workers`): `--workers auto` starts at
the currently-free core count (`cores − load average`) and a background `_controller`
thread nudges the target up when load < 0.90×ncpu and down when > 1.05×ncpu (checked every
8 s), so it uses all the headroom it can without hurting co-located work (e.g. a runner
fleet). A `ThreadPoolExecutor` caps at `ncpu`; an in-flight gate (`Condition`) holds
submissions to the live `target`. Per-file errors are caught and counted — a bad file never
stops the batch. `resume=True` skips existing outputs. The manifest's `avg_s` is
**wall-clock** seconds-per-file (honest ETA under parallelism, not per-worker mean).

**Copy** (`copytree.copy_tree`): recursively mirror `src → dst` preserving structure and
metadata (`shutil.copy2`), pre-creating the dir tree once. Restart-safe: a destination that
already exists **with the same size** is skipped (implicit resume). Bulk copy is I/O-bound,
so it holds a fixed pool (`max(2, free-cpu)` for `auto`) — the disk is the ceiling, not CPU.
Writes an optional running manifest (files/s, GB).

## Fan-out

Two complementary models, both exposed as workflows:

- **`ConvertBatch(paths, out_dir)`** — `andThen foreach path in $.paths`, one `ConvertRaw`
  task **per file across the fleet**. Fleet-level parallelism (each file a task).
- **`ConvertDir(in_dir, out_dir, …)`** — **one step**, one `ConvertTree` task that does the
  whole directory with **N threads inside the single task** (the adaptive engine).
- **`CopyDir(src, dst)`** — one `CopyTree` step, multi-threaded within the task.

So conversion parallelises either *across the fleet* (one task per file) or *within a task*
(one multi-threaded step over a directory) — pick fleet fan-out for many hosts, the
single-step engine for one host's cores.

## Data & fields

- **Inputs:** RAW `.nef/.nrw/.cr2/.cr3/.crw/.arw/.srf/.sr2/.dng/.raf/.orf/.rw2/.pef/.srw`
  (`images.RAW_EXTS`) + `.jpg/.jpeg/.png/.webp/.bmp/.tif/.tiff/.heic/.heif`.
- **Facet params:** `out_format` (`tif`/`jpeg`), `resize` (`N|WxH|50%`, empty = original),
  `from_sel` (`raw|any|<ext list>`), `recursive`, `quality`, `workers`, `highlight_mode`.
- **Summary fields:** `converted`, `skipped`, `failed` (facet returns); the CLIs add
  `total`, `workers_peak`, `elapsed_seconds`, `in_dir`/`out_dir`, and (copy) `gb`,
  `files_per_s`.

## External libraries / binaries

- **`opencv-python`** (core) — resize.
- **`tifffile`** (core) — 16-bit TIFF write.
- **`Pillow` / `numpy`** (core) — JPEG encode, array math.
- **`rawpy` / LibRaw** (extra `[raw]`, **binary**-backed) — needed only for RAW inputs;
  TIFF/JPEG/HEIC conversion runs on the core deps.
- **`pillow-heif`** (core) — decode `.heic/.heif` inputs.
- stdlib only for the parallel/copy machinery (`concurrent.futures`, `threading`, `shutil`,
  `os.getloadavg`).

## Facets & workflows

| Facet / Workflow | Kind | Effect | Purpose (from FFL docstring) |
|---|---|---|---|
| `Ingest.ListImages(in_dir)` → `(paths, count)` | event | io | List processable image/RAW files in a directory. |
| `Ingest.ConvertRaw(image_path, out_dir, highlight_mode="clip")` → `(output)` | event | io | Convert one RAW/image → full-res 16-bit TIFF (verbatim, no crop/enhance). |
| `Ingest.ConvertTree(in_dir, out_dir, out_format="tif", resize="", from_sel="raw", recursive=true, quality=95, workers="auto")` → `(converted, skipped, failed)` | event | io | Convert a whole dir/tree → TIFF/JPEG with the adaptive multi-threaded engine. |
| `Ingest.CopyTree(src, dst, workers="auto")` → `(copied, skipped, failed)` | event | io | Recursively copy a tree, multi-threaded + restart-safe. |
| `workflows.ConvertBatch(paths, out_dir)` → `(count)` | workflow | — | Fan out per file across the fleet (one `ConvertRaw` task/photo). |
| `workflows.ConvertDir(in_dir, out_dir, …)` → `(converted)` | workflow | — | One multi-threaded `ConvertTree` step. |
| `workflows.CopyDir(src, dst)` → `(copied)` | workflow | — | One multi-threaded `CopyTree` step. |

`nef_to_tif.py` is a thin **back-compat alias** for `convert_photos.py` (re-exports its
functions, defaults RAW→TIFF); the `.sh` wrappers source the repo `.venv` and `exec` the
Python CLI.

## Cache / output

Outputs land in `out_dir` (mirroring the input tree for `convert_tree`): `<stem>.tif`
(16-bit deflate) or `<stem>.jpg`. Recursive convert writes `_convert_manifest.json`; copy
writes `_copy_manifest.json` (handler passes `dst/_copy_manifest.json`). Local paths only.

## Gotchas & notes

- **`convert_tree` mirrors relative structure**; `convert_dir` is one level. Recursive
  default inputs are **RAW only** (`from_sel="raw"`) unless you widen with `--from any` or
  an ext list — a deliberate guard so a tree convert doesn't re-process already-derived JPEGs.
- **Resume is by output existence** (convert) / **same-size destination** (copy) — cheap and
  idempotent, but it won't re-do a partially-written or truncated output; delete it to force.
- **`auto` yields to co-located load** — on a busy runner host the pool shrinks; pin
  `--workers N` (or `1` for serial) for deterministic throughput.
- **`convert_one` is verbatim** — no crop, no enhancement; the enhance path is a separate
  feature ([enhance-pipeline](enhance-pipeline.md)).

## Related specs

- [image-io](image-io.md) — `load_image16`/`save_tiff16` and RAW/HEIC/TIFF handling that
  conversion is built on; also the `tiffs-to-jpegs` derive step.
- [enhance-pipeline](enhance-pipeline.md) — `ListImages` feeds `EnhanceBatch`.
- [domain-and-cache](domain-and-cache.md) — handler registration + the by-reference contract.
