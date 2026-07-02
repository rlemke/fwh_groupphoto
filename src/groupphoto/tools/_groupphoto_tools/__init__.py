"""Shared library behind the groupphoto tools + (future) handlers.

Package-unique name (``_groupphoto_tools``) per the tools-pattern contract so it
never collides in ``sys.modules`` with other co-installed domain packages.

Modules:
    images   — load/save/normalize images (Pillow); 16-bit RAW + TIFF; highlight recovery
    crop     — pure box geometry + cropping + cutout compositing (no models; testable)
    quality  — sharpness / focus / exposure scoring (no models)
    detect   — person detection (YOLO) with an offline mock
    enhance  — dehaze / auto-brighten / unsharp / upscale / face-restore (graceful fallbacks)
    glare    — glare & highlight correction (DCP dehaze + CLAHE; RAW highlight recovery)
    deblur   — deblur/sharpen orchestration (face-restore + unsharp)
    background — person matting (rembg) + background composite (blur/bokeh/image)
    pipeline — whole-photo orchestration: load → glare → deblur → tone → [bg] → save
    groupphoto_mocks — deterministic offline detector/matte for tests / --use-mock
    sidecar/storage — cache primitives (agent-spec/cache-layout)
"""

NAMESPACE = "groupphoto"
