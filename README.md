# fwh_groupphoto

Enhance **posed group-gathering photos** — a family/team/reunion shot where people
have arranged themselves for one picture. Unlike the per-rider cycling pipeline
([fwh_peloton](https://github.com/rlemke/fwh_peloton), which this reuses), it produces
**one enhanced photo per input** (the whole frame, faces fixed in place) and can
optionally swap the background.

```
group photo (RAW/JPEG/HEIC)
  → load 16-bit (+ RAW highlight recovery)
  → glare: CLAHE local-contrast (+ optional dark-channel dehaze)
  → tone: auto-brighten (metered on the people) + black/white-point dehaze  [16-bit, banding-free]
  → deblur: whole-frame unsharp + optional face restoration (GFPGAN/CodeFormer)
  → [optional] background: matte the group → composite onto blur / bokeh / a supplied image
  → out/<stem>_enhanced.{tif,jpg}
```

Three corrections, honest about what's recoverable:

- **Blurriness** — face restoration reconstructs soft faces (the perceptual win in a
  group shot) + a gentle global unsharp. A dedicated deblur model (NAFNet) is opt-in/phase 2.
- **Glare** — veiling sun-haze is genuinely fixable (CLAHE + optional dehaze). Blown
  windows behind the group are best recovered **at RAW decode** (`--highlight-mode`);
  fully-clipped pixels carry no data (only hideable by inpainting, phase 2). Eyeglass
  glare that occludes the eyes is left alone — inpainting would fabricate eyes.
- **Prettier background** (`--background`) — matte the group and composite onto a blurred
  version of the same frame, a bokeh blur, or a supplied image. AI-generated backdrops are
  phase 3.

A Facetwork domain package following the tools/handlers pattern. This ships the reusable
**library + CLI tools** (`src/groupphoto/tools/`); the FFL handlers/workflow (→ a fleet
runner) are the next phase.

## Tools

| Tool | Does |
|------|------|
| `enhance-group`  | One photo → one enhanced photo (glare + deblur + optional new bg) |
| `batch-group`    | A directory → enhanced outputs + running `manifest.json` (`--resume`) |
| `replace-bg`     | Just the background step (matte + composite) on one photo |
| `tiffs-to-jpegs` | Derive shareable 8-bit JPEGs from the 16-bit TIFF masters |
| `convert-photos` | Convert **RAW/TIFF/JPEG → TIFF or JPEG** at any resolution (`--format`/`--resize`), recursive + adaptive-parallel. (`nef-to-tif` is a RAW→TIFF alias.) |
| `copy-tree`      | Parallel recursive directory copy — mirror a tree, restart-safe (`--workers`) |

Every tool: JSON on **stdout**, logs on **stderr**, `--use-mock` (offline, no models),
`--log-level`. Heavy ML deps are **optional extras, lazily imported** — the pipeline
degrades gracefully (glare/tone/sharpen run on the core deps alone; face-restore →
passthrough, matte → background change skipped, when their extras are absent).

## Quick start

```bash
pip install -e '.[detect,enhance,matte,raw]'      # full; core alone runs degraded

# a group RAW → cleaned up, lossless 16-bit TIFF (default: keep original background):
python src/groupphoto/tools/enhance_group.py --image group.NEF --out-dir out/

# recover blown windows + a bokeh background, as a shareable JPEG:
python src/groupphoto/tools/enhance_group.py --image group.NEF --out-dir out/ \
    --highlight-mode reconstruct --background bokeh --out-format jpg

# a whole folder, resumable:
python src/groupphoto/tools/batch_group.py --in-dir photos/ --out-dir out/ \
    --background blur --out-format tiff --resume

# derive JPEGs from the TIFF masters:
python src/groupphoto/tools/tiffs_to_jpegs.py --in-dir out/ --out-dir out_jpg/

# convert RAW/TIFF/JPEG → TIFF or JPEG, any resolution (convert-photos):
python src/groupphoto/tools/convert_photos.py --image shot.NEF --out-dir out/                 # RAW → 16-bit TIFF, full res
python src/groupphoto/tools/convert_photos.py --image master.tif --out-dir out/ --format jpeg --resize 2048  # TIF → JPEG, long edge 2048
python src/groupphoto/tools/convert_photos.py --in-dir jpgs/ --out-dir tifs/ --from jpg      # JPEG → TIFF
# a whole tree, mirroring structure (RAW → JPEG @ 3000px), resumable + adaptive-parallel:
python src/groupphoto/tools/convert_photos.py --in-dir shoots/ --out-dir out/ --recursive --format jpeg --resize 3000 --resume
#   --format tif|jpeg · --quality N · --resize N|WxH|50% · --from raw|any|<ext list>
#   --workers auto (default): sizes to free CPUs, ramps up on headroom, backs off on saturation
```

## Run as an FFL workflow

The tools are exposed as a Facetwork domain (`facetwork.domains` entry point +
`handlers/` + `ffl/groupphoto.ffl`), so the pipeline runs on the runtime / fleet.

Event facets (image data flows **by reference** — file/MinIO paths):
- `groupphoto.Enhance.EnhanceGroup(image_path, out_dir, background, …)` → `(output, n_people)`
- `groupphoto.Enhance.ReplaceBackground(image_path, out_dir, mode, bg_image)` → `(output)`
- `groupphoto.Ingest.ConvertRaw(image_path, out_dir, highlight_mode)` → `(output)`
- `groupphoto.Ingest.ConvertTree(in_dir, out_dir, out_format, resize, from_sel, …)` → `(converted, skipped, failed)` — **multi-threaded** whole-directory/tree convert (RAW/TIFF/JPEG → TIFF/JPEG)
- `groupphoto.Ingest.CopyTree(src, dst, workers)` → `(copied, skipped, failed)` — **multi-threaded** recursive copy
- `groupphoto.Ingest.ListImages(in_dir)` → `(paths, count)`

Workflows: `EnhanceOne`, `EnhanceBatch(paths, out_dir, background)` (fan out per photo),
`ConvertBatch(paths, out_dir)` (fleet fan-out, one task/file), `ConvertDir(in_dir, out_dir, …)`
(one step, multi-threaded), `CopyDir(src, dst)`.

The **multi-threaded** conversion/copy engine (adaptive `--workers auto` — sizes to free
CPUs, ramps up on headroom, backs off on saturation) is shared by the CLIs
(`convert-photos`, `copy-tree`) and these handlers.

```bash
pip install -e '.[detect,enhance,matte,raw,domain]'      # domain = the facetwork runtime
facetwork compile src/groupphoto/ffl/groupphoto.ffl --check
python -m facetwork.domains --seed groupphoto            # register handlers + seed the flows
```

## Extras (optional, lazy-imported — pipeline degrades gracefully without them)

| Extra | Enables |
|-------|---------|
| `detect`  | Person detection for exposure metering + headcount (ultralytics/torch) |
| `enhance` | Face restoration — GFPGAN/CodeFormer (spandrel/gfpgan) |
| `matte`   | Background matting — BiRefNet/isnet via `rembg` (onnxruntime) |
| `raw`     | Camera RAW decode + highlight recovery (rawpy/LibRaw) |
| `inpaint` | *(phase 2)* LaMa inpaint for blown windows / speculars (iopaint) |
| `ai`      | *(phase 3)* AI-generated backgrounds (diffusers/transformers) |
| `s3`      | S3/MinIO storage (boto3) |
| `domain`  | Run as an FFL workflow on the Facetwork runtime (facetwork) |

Model weights cache under `~/.cache/groupphoto/weights`. Reuse fwh_peloton's already-
downloaded GFPGAN/RealESRGAN weights by symlinking that dir if present.

## Layout

```
src/groupphoto/
  tools/
    enhance_group batch_group replace_bg tiffs_to_jpegs convert_photos copy_tree  (+ .sh)
    _groupphoto_tools/
      images crop quality detect enhance segment sidecar storage  (reused from fwh_peloton)
      glare deblur background pipeline copytree groupphoto_mocks  (new)
  ffl/groupphoto.ffl   event facets + workflows
  handlers/            ingest/ (list/convert/convert-tree/copy-tree) + enhance/ + shared/ shim
tests/                 offline suite (35 tests, no network/models via --use-mock)
```

## Tests

```bash
pip install -e '.[test]' && pytest -q          # all offline
```

## Status

Phase 1 (v1) — the tools library + CLIs. Deblur = face-restore + unsharp; glare = CLAHE +
RAW highlight recovery + optional DCP dehaze; background = none/blur/bokeh/image via
rembg-BiRefNet matte. Phase 2 (LaMa inpaint, NAFNet `--deblur`), phase 3 (AI backgrounds),
and phase 4 (`facetwork.domains` entry point → fleet runner) are planned.
