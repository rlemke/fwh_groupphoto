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
        "groupphoto.Ingest.ConvertTree",
        "groupphoto.Ingest.CopyTree",
        "groupphoto.Enhance.EnhanceGroup",
        "groupphoto.Enhance.ReplaceBackground",
    }


def test_convert_tree_and_copy_tree_handlers(tmp_path):
    from PIL import Image

    from groupphoto.handlers.ingest.ingest_handlers import handle
    src = tmp_path / "in" / "e1"
    src.mkdir(parents=True)
    for n in ("a", "b"):
        Image.fromarray(np.random.default_rng(4).integers(0, 256, (60, 90, 3)).astype("uint8")).save(src / f"{n}.jpg")
    # multi-threaded whole-tree convert (jpg → tif), via the dispatch entrypoint
    r1 = handle({"_facet_name": "groupphoto.Ingest.ConvertTree", "in_dir": str(tmp_path / "in"),
                 "out_dir": str(tmp_path / "tif"), "from_sel": "jpg", "workers": 2})
    assert r1 == {"converted": 2, "skipped": 0, "failed": 0}
    assert (tmp_path / "tif" / "e1" / "a.tif").is_file()
    # multi-threaded recursive copy
    r2 = handle({"_facet_name": "groupphoto.Ingest.CopyTree", "src": str(tmp_path / "tif"),
                 "dst": str(tmp_path / "copy"), "workers": 2})
    assert r2["copied"] >= 2 and r2["failed"] == 0
    assert (tmp_path / "copy" / "e1" / "a.tif").is_file()


def test_enhance_group_handler_mock(tmp_path):
    from PIL import Image

    from groupphoto.handlers.enhance.enhance_handlers import handle
    p = tmp_path / "g.jpg"
    Image.fromarray(np.random.default_rng(2).integers(0, 256, (300, 400, 3)).astype("uint8")).save(p)
    out = handle({"_facet_name": "groupphoto.Enhance.EnhanceGroup", "image_path": str(p),
                  "out_dir": str(tmp_path / "o"), "use_mock": True, "out_format": "jpg",
                  "background": "blur"})
    assert out["n_people"] == 4 and out["output"].endswith("_enhanced.jpg")
