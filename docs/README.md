# fwh_groupphoto — Feature Specifications

This directory holds one **spec per feature** of the group-photo enhancement domain. Each
document follows a common shape ([`SPEC_TEMPLATE.md`](SPEC_TEMPLATE.md)) and states, for
that feature: how it works, whether and how it **fans out** across the fleet, the **data &
fields** it reads/writes, the **external libraries/binaries** it relies on, its **facets &
workflows**, and its **cache/output**. Claims are grounded in the FFL `/** … */`
docstrings, the handler code, and the `_groupphoto_tools` library — the source of truth for
each facet remains its FFL docstring; these specs are the feature-level narrative over them.

**Start here:** [**Enhance Pipeline**](enhance-pipeline.md) — the flagship feature (one
posed group photo → one enhanced photo: glare + tone + deblur + optional background),
orchestrating the four correction stages below.

## The enhance pipeline

| Spec | What it covers |
|------|----------------|
| [enhance-pipeline.md](enhance-pipeline.md) | **Flagship.** Whole-frame orchestration (`EnhanceGroup`, `EnhanceOne`/`EnhanceBatch`, the `enhance-group`/`batch-group` CLIs); load → detect/meter → glare → tone → deblur → background → save; the tone-cleanup stage (`auto_brighten16`/`dehaze16`). |

## Correction stages

| Spec | What it covers |
|------|----------------|
| [glare.md](glare.md) | Glare & highlight correction — CLAHE local-contrast, dark-channel-prior dehaze, and RAW `highlight_mode` recovery for blown windows; honest about what's unrecoverable. |
| [deblur.md](deblur.md) | Deblur — whole-frame unsharp + GFPGAN/CodeFormer face restoration (the perceptual win); the 8-bit precision trade-off; dormant Real-ESRGAN upscale. |
| [background.md](background.md) | Background replacement — rembg/BiRefNet whole-group matte + composite onto blur/bokeh/image/color (`ReplaceBackground` facet, `replace-bg` CLI). |
| [detect.md](detect.md) | Person detection & exposure metering — YOLO person boxes → the "where the group is" region (meter a backlit group) + headcount; advisory and fail-open. |

## Ingest, conversion & I/O

| Spec | What it covers |
|------|----------------|
| [conversion.md](conversion.md) | The adaptive multi-threaded convert/copy engine — RAW/TIFF/JPEG → TIFF/JPEG at any resolution + mirror-copy trees (`ConvertRaw`/`ConvertTree`/`CopyTree`/`ListImages`, `ConvertBatch`/`ConvertDir`/`CopyDir`, `convert-photos`/`nef-to-tif`/`copy-tree`). |
| [image-io.md](image-io.md) | The shared I/O layer — 16-bit load/save, RAW (rawpy/LibRaw) + HEIC (pillow-heif) + TIFF (tifffile) handling, and the `tiffs-to-jpegs` derive step. |

## Domain, cache & reused code

| Spec | What it covers |
|------|----------------|
| [domain-and-cache.md](domain-and-cache.md) | How the tools become a Facetwork domain (entry point, handler registration, the by-reference contract); the **present-but-unwired** `storage`/`sidecar` cache infra; the **reused-from-`fwh_peloton`, currently dormant** modules (`segment`, `quality`, `crop.cutout`, `upscale`). Read before assuming a facet is served or a cache is used. |
| [ffl-examples.md](ffl-examples.md) | **Usage patterns.** A gallery of complete, compile-checked FFL examples over these facets — list→`foreach` fan-out, chained per-image steps, `catch` per photo, `when` guards, call-time mixins. |

---

*See also the repo [`README.md`](../README.md) (tools, extras, quick start, layout) and the
live/queryable interface: the MCP `fw_capabilities` (facets by intent) and
`fw_describe_handler` tools once the domain is seeded (`python -m facetwork.domains --seed
groupphoto`).*
