# Domain Wiring, Cache & Reused Code

**Namespace:** all (`groupphoto`, `groupphoto.Ingest`, `groupphoto.Enhance`,
`groupphoto.workflows`) · **FFL:** `src/groupphoto/ffl/groupphoto.ffl` ·
**Entry point:** `src/groupphoto/__init__.py` (`facetwork.domains`) ·
**Handlers:** `src/groupphoto/handlers/{__init__,ingest/ingest_handlers,enhance/enhance_handlers,shared/groupphoto_utils}.py` ·
**Cache infra:** `_groupphoto_tools/{storage,sidecar}.py` ·
**Tests:** `tests/test_ffl_domain.py`

## Overview

This is the honest, cross-cutting spec: how the tools become a Facetwork domain that runs
on the runtime/fleet, how images flow **by reference**, and — importantly — which
infrastructure is **present but not yet wired in** and which modules are **reused from
`fwh_peloton` and currently dormant** in the group pipeline. It's the boundaries spec: read
it before assuming a facet is served, a cache is used, or a module runs.

## How it works

- **Domain discovery.** `groupphoto/__init__.py` builds
  `domain = DomainPackage(name="groupphoto", ffl_dir=…/ffl, register_handlers=register_all_registry_handlers)`,
  exported via the `[project.entry-points."facetwork.domains"] groupphoto = "groupphoto:domain"`
  in `pyproject.toml`. The whole block is wrapped in `try/except ImportError` so
  **tools/tests run in a facetwork-less venv** (`domain = None` then) — the tools import
  `_groupphoto_tools` directly, never `import groupphoto`.
- **Handler registration.** `register_all_registry_handlers(runner)` calls the ingest then
  enhance `register_handlers`, each of which loops a `_DISPATCH` table and calls
  `runner.register_handler(facet_name=…, module_uri=__name__, entrypoint="handle")`. At
  runtime `handle(payload)` dispatches on `payload["_facet_name"]`. Six facets register
  (asserted exactly in `test_domain_registers_expected_facets`): `Ingest.ListImages`,
  `Ingest.ConvertRaw`, `Ingest.ConvertTree`, `Ingest.CopyTree`, `Enhance.EnhanceGroup`,
  `Enhance.ReplaceBackground`.
- **The shim.** `handlers/shared/groupphoto_utils.py` puts `tools/` on `sys.path` and
  imports `_groupphoto_tools` (`background`, `copytree`, `images`, `pipeline`) + the
  tools-level `convert_photos` module by their package-unique names — the same way the CLIs
  do — so handlers and CLIs share one implementation.
- **By-reference data flow.** Every facet declares `with Effect(kind = "io")` and passes
  **paths**, not pixels: `image_path`/`in_dir`/`out_dir`/`src`/`dst` strings in, an
  `output`/counts summary out. This keeps large RAW/TIFF payloads off the task bus.

## Fan-out

Covered per feature — `EnhanceBatch`/`ConvertBatch` fan out per photo/file across the
fleet; `ConvertDir`/`CopyDir` are single multi-threaded steps. See
[enhance-pipeline](enhance-pipeline.md) and [conversion](conversion.md).

## Data & fields

Facet signatures and returns are enumerated in the per-feature specs. The one schema,
`groupphoto.EnhanceResult { output: String, n_people: Long }`, is declared in the top-level
`groupphoto` namespace.

## External libraries / binaries

- **`facetwork`** (extra `[domain]`, `>=0.31.0`) — only needed to run as a workflow; the
  tools/library install and test fine without it.
- **`boto3`** (extra `[s3]`) — used *only* by `storage.py` (see the cache note below).

## Facets & workflows

The full set (2 namespaces of event facets + 5 workflows) is documented across
[enhance-pipeline](enhance-pipeline.md), [background](background.md), and
[conversion](conversion.md). All facets are **event** facets (`Effect(kind="io")`); no
`Cost` mixins are declared. No pure/compute facets exist — every capability is I/O-bound
image work.

## Cache / output

- **Handlers write to a local `out_dir`.** `handle_enhance_group`, `handle_convert_raw`,
  `handle_replace_background`, etc. `mkdir` the destination and write with
  `images.save_tiff16`/`save_image` (or the convert/copy engines). They do **not** route
  through a storage backend or a cache sidecar.
- **`_groupphoto_tools/storage.py` (local | s3/MinIO) and `sidecar.py` (per-entry
  `.meta.json` cache) exist and are complete** — `storage` dispatches `read_bytes`/
  `write_bytes`/`exists`/`list_files` on the path (local dir or `s3://…`), and `sidecar`
  implements a contention-free per-key cache under `<cache_root>/groupphoto/<type>/…`
  conforming to `agent-spec/cache-layout`. **But nothing in the handlers or the pipeline
  imports them yet** (verified: no importers outside the two modules). They are scaffolding
  for a future MinIO-backed cache/output; today outputs are local files. Treat the module
  docstrings' "s2 tools" / "map bundle" wording as copied-from-a-template — this domain
  emits photos, not maps.
- The **`.env`/`FW_STORAGE`/`FW_S3_*`** contract the modules read matches the runtime's, so
  wiring them in later is a drop-in, not a redesign.

## Gotchas & notes

- **README status vs. reality.** The repo README's top line says the FFL handlers/workflow
  are "the next phase" and lists phase 4 as "planned," but the domain **is** implemented and
  tested (`__init__.py` entry point + `handlers/` + `test_ffl_domain.py` register and run
  the six facets). The README's *later* "Run as an FFL workflow" section is the accurate
  one; the intro line lags.
- **Reused-from-`fwh_peloton`, currently dormant** (present in `_groupphoto_tools`, not
  reached by any group-photo facet/CLI or the pipeline — verified no importers):
  - `segment.py` — box-prompted SAM per-rider cutout masks.
  - `quality.py` — model-free sharpness/exposure scoring (best-shot ranking).
  - `crop.py`'s `cutout` / `aspect_box` / `context_box` — per-object cutouts and
    aspect-crop geometry (only `union`/`pad_box`/`clamp_box`/`area`/`intersects` are live,
    via `detect.people_union_box`).
  - `enhance.py`'s `upscale` / Real-ESRGAN path and the 8-bit `auto_brighten`/`dehaze` (the
    pipeline uses the 16-bit `*16` variants).
  Keep them — they're the shared cross-domain library — but don't assume they run here.
- **Handler-layer defaults differ from CLI defaults.** e.g. `EnhanceGroup` handler defaults
  `face_restore=False` (fast, no weights) while the `enhance-group` CLI defaults it on. Pass
  the param explicitly when it matters.

## Related specs

- [enhance-pipeline](enhance-pipeline.md), [conversion](conversion.md),
  [background](background.md) — the facets registered here.
- [image-io](image-io.md) — the save functions the handlers call directly (bypassing the
  dormant `storage`/`sidecar`).
- [detect](detect.md), [deblur](deblur.md) — the other homes of the dormant reused code
  (`segment`, `crop.cutout`, `enhance.upscale`).
