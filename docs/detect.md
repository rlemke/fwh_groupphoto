# Person Detection & Exposure Metering

**Namespace:** (no facet of its own — an advisory stage of `groupphoto.Enhance.EnhanceGroup`) ·
**Tools:** `src/groupphoto/tools/_groupphoto_tools/detect.py`,
`_groupphoto_tools/crop.py` (box geometry) ·
**Tests:** exercised via `tests/test_pipeline_mock.py` / `test_ffl_domain.py` (mock people)

## Overview

Find each person in the frame and use the boxes to (a) **meter exposure on the people**
(not the whole frame — a group backlit by a window is dark even when the frame averages
bright), and (b) report a **headcount** (`n_people`). Unlike the cycling pipeline there is
**no per-person crop step** here — detection is purely advisory to the enhance, and the
boxes are combined into one "where the group is" region.

## How it works

`detect.detect_people(img, conf=0.25, backend="yolo", model="yolo11x.pt", use_mock=False)`:

- `use_mock=True` → `groupphoto_mocks.mock_people` returns 4 evenly-spaced deterministic
  boxes (offline/tests).
- `backend="yolo"` → `_detect_yolo` runs Ultralytics YOLO `predict(conf=…, classes=[0])`
  (COCO `person` class), models cached in `_MODEL_CACHE`.

People are returned as `Person(box, score, index, meta)` dataclasses, **sorted
largest-first** (nearest first) and re-indexed `0..N-1`. `people_union_box(people, w, h,
pad_frac=0.05)` computes the smallest box enclosing all people (via `crop.union` +
`crop.pad_box`), clamped to the image — that box is what the pipeline slices as the
**exposure meter** for `auto_brighten16`.

In `pipeline.enhance_group`, the entire detect step is wrapped in `try/except` and logged
as advisory: **detection failure never aborts the enhance** — it just falls back to
whole-frame metering. `n_people` is carried into the output summary.

## Fan-out

Not applicable — an in-memory stage of a single `EnhanceGroup`.

## Data & fields

Knobs: `--no-detect` (skip detection/metering entirely), `--conf` (default 0.25),
`--model` (default `yolo11x.pt`). Emits `n_people` in the pipeline summary. The union box
is internal (drives metering); it is not written out.

## External libraries / binaries

- **`ultralytics`** + **`torch`** (extra `[detect]`) — YOLO detection. **Optional**: if
  absent, `_load_yolo` raises a clear install message; the CLI/pipeline path that reaches
  it is only taken when `detect_people=True` and not `use_mock`. Run with `--no-detect` or
  `--use-mock` to avoid the dependency.
- **`numpy`** (core) — box math in `crop.py` (pure, deterministic — carries the crop-geometry
  unit tests).

## Facets & workflows

None of its own. Detection is step "0" of `pipeline.enhance_group`, gated by `detect_people`
(CLI `--no-detect`), `conf`, and `detect_model`. It has no independent facet or workflow.

## Cache / output

No artifact — its only externally-visible output is the `n_people` field and the (internal)
metering region. Models cache under Ultralytics' own weights cache.

## Gotchas & notes

- **Metering region, not a crop.** The union box exists to fix exposure on a backlit group;
  it is deliberately not used to crop or cut out individuals (that's the cycling pipeline's
  job). `pad_frac=0.05` gives a little margin.
- **Advisory and fail-open** — any detector error → warn + whole-frame metering, never a
  pipeline abort.
- **`segment.py` (box-prompted SAM per-rider masks) is reused-from-`fwh_peloton` and
  dormant** here — the group pipeline never segments individuals. Same for
  `crop.cutout`/`aspect_box`/`context_box`. See [domain-and-cache](domain-and-cache.md).

## Related specs

- [enhance-pipeline](enhance-pipeline.md) — consumes the metering box in the tone stage.
- [background](background.md) — mattes the group semantically (rembg), independent of these boxes.
- [domain-and-cache](domain-and-cache.md) — the dormant segment/cutout inventory.
