"""Person detection for group photos — find each person in the frame.

We run an object detector (Ultralytics YOLO by default) and keep the ``person``
class. Unlike the cycling pipeline there is no per-person crop step; the boxes are
used to *meter exposure on the people* (not the whole frame — a group backlit by a
window is dark even when the frame averages bright), to report a headcount, and to
optionally scope face/skin work.

Backends:
    use_mock=True  → deterministic boxes from ``groupphoto_mocks`` (offline / tests)
    backend="yolo" → Ultralytics YOLO (lazy import; ``pip install '.[detect]'``)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from _groupphoto_tools import crop as _crop

NAMESPACE = "groupphoto"
log = logging.getLogger("groupphoto.detect")

_COCO_PERSON = 0
_MODEL_CACHE: dict[str, Any] = {}


@dataclass
class Person:
    """One detected person: a bounding box + the detector's confidence."""

    box: _crop.Box
    score: float
    index: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "score": round(float(self.score), 4),
            "box": [round(float(v), 1) for v in self.box],
            **({"meta": self.meta} if self.meta else {}),
        }


def _load_yolo(model: str) -> Any:
    if model in _MODEL_CACHE:
        return _MODEL_CACHE[model]
    try:
        from ultralytics import YOLO  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "Person detection needs Ultralytics YOLO. Install it:\n"
            "    pip install '.[detect]'   (or: pip install ultralytics)\n"
            "Or run with use_mock=True / --use-mock for the offline path."
        ) from exc
    log.info("loading YOLO weights: %s", model)
    m = YOLO(model)
    _MODEL_CACHE[model] = m
    return m


def detect_people(
    img: Any,
    *,
    conf: float = 0.25,
    backend: str = "yolo",
    model: str = "yolo11x.pt",
    use_mock: bool = False,
) -> list[Person]:
    """Detect people in a ``PIL.Image``. Returns people sorted largest-first
    (nearest first), re-indexed 0..N-1."""
    if use_mock:
        from _groupphoto_tools import groupphoto_mocks  # noqa: PLC0415
        people = groupphoto_mocks.mock_people(img)
    elif backend == "yolo":
        people = _detect_yolo(img, conf=conf, model=model)
    else:
        raise ValueError(f"unknown detect backend: {backend!r}")

    people.sort(key=lambda p: _crop.area(p.box), reverse=True)
    for i, p in enumerate(people):
        p.index = i
    log.info("detected %d person(s)", len(people))
    return people


def _detect_yolo(img: Any, *, conf: float, model: str) -> list[Person]:
    m = _load_yolo(model)
    results = m.predict(img, conf=conf, classes=[_COCO_PERSON], verbose=False)
    people: list[Person] = []
    for res in results:
        for b in res.boxes:
            box = tuple(float(v) for v in b.xyxy[0].tolist())
            people.append(Person(box=box, score=float(b.conf[0])))  # type: ignore[arg-type]
    log.info("yolo: %d person box(es)", len(people))
    return people


def people_union_box(people: list[Person], width: int, height: int,
                     *, pad_frac: float = 0.0) -> _crop.Box | None:
    """Smallest box enclosing all people (padded, clamped) — the 'where the group
    is' region, used to meter exposure. None if no people."""
    if not people:
        return None
    base = _crop.union(*[p.box for p in people])
    return _crop.pad_box(base, pad_frac, width, height)
