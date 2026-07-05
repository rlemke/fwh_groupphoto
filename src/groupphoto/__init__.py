"""groupphoto — enhance posed group-gathering photos (deblur + glare + optional bg).

The reusable **library + tools** live under ``tools/``; the ``facetwork.domains``
entry point below (with ``handlers/`` + ``ffl/``) exposes them as FFL workflows so
the pipeline runs on the Facetwork runtime / fleet.
"""

from __future__ import annotations

__version__ = "0.1.0"

# The FFL-workflow layer. Guarded so the tools/tests (which import _groupphoto_tools
# directly, never `import groupphoto`) still work in a facetwork-less venv.
try:
    from pathlib import Path

    from facetwork.domains import DomainPackage

    from .handlers import register_all_registry_handlers

    domain = DomainPackage(
        name="groupphoto",
        ffl_dir=Path(__file__).parent / "ffl",
        register_handlers=register_all_registry_handlers,
    )
except ImportError:  # facetwork not installed — tools-only mode
    domain = None
