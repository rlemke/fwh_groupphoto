"""FFL-workflow layer — domain discovery, handler registration, handler execution.

Skipped where facetwork isn't installed (the tools/library run without it)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("facetwork")
import groupphoto  # noqa: E402


def test_domain_registers_expected_facets():
    assert groupphoto.domain is not None and groupphoto.domain.name == "groupphoto"

    class FakeRunner:
        def __init__(self):
            self.names: set[str] = set()

        def register_handler(self, facet_name, module_uri, entrypoint="handle", **kw):
            self.names.add(facet_name)

    r = FakeRunner()
    groupphoto.domain.register_handlers(r)
    assert r.names == {
        "groupphoto.Ingest.ListImages",
        "groupphoto.Ingest.ConvertRaw",
        "groupphoto.Enhance.EnhanceGroup",
        "groupphoto.Enhance.ReplaceBackground",
    }


def test_enhance_group_handler_mock(tmp_path):
    from PIL import Image

    from groupphoto.handlers.enhance.enhance_handlers import handle
    p = tmp_path / "g.jpg"
    Image.fromarray(np.random.default_rng(2).integers(0, 256, (300, 400, 3)).astype("uint8")).save(p)
    out = handle({"_facet_name": "groupphoto.Enhance.EnhanceGroup", "image_path": str(p),
                  "out_dir": str(tmp_path / "o"), "use_mock": True, "out_format": "jpg",
                  "background": "blur"})
    assert out["n_people"] == 4 and out["output"].endswith("_enhanced.jpg")
