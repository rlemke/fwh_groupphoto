"""Bridge from the handlers to the internal ``_groupphoto_tools`` library.

``tools/`` is deliberately not a Python package; we put it on ``sys.path`` and import
``_groupphoto_tools`` by its package-unique name — the same way the CLIs do.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from _groupphoto_tools import background, images, pipeline  # noqa: E402,F401

__all__ = ["background", "images", "pipeline"]
