"""Deterministic offline mocks — for tests and ``--use-mock``.

Return fixed people boxes and a fixed foreground matte so the whole
load → glare → deblur → tone → [background] → save pipeline can be exercised with
no models and no network. Everything scales with the image so it stays in-bounds.
"""

from __future__ import annotations

from typing import Any

from _groupphoto_tools.detect import Person


def mock_people(img: Any, n: int = 4) -> list[Person]:
    """``n`` evenly-spaced people across the middle band of the image."""
    w, h = int(img.width), int(img.height)
    people: list[Person] = []
    cell = w / n
    pw = cell * 0.6
    ptop, pbot = h * 0.20, h * 0.85
    for i in range(n):
        cx = cell * (i + 0.5)
        box = (cx - pw / 2, ptop, cx + pw / 2, pbot)
        people.append(Person(box=box, score=0.90 - 0.05 * i, index=i, meta={"mock": True}))
    return people


def mock_matte(width: int, height: int) -> Any:
    """A deterministic foreground alpha (``uint8`` HxW, 0..255): a central band
    that stands in for 'the group' so background compositing can be tested."""
    import numpy as np  # noqa: PLC0415

    a = np.zeros((height, width), dtype="uint8")
    x1, x2 = int(width * 0.10), int(width * 0.90)
    y1, y2 = int(height * 0.18), int(height * 0.88)
    a[y1:y2, x1:x2] = 255
    return a
