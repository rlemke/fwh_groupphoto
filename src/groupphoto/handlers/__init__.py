"""Register all groupphoto RegistryRunner handlers (deferred imports)."""

from __future__ import annotations


def register_all_registry_handlers(runner) -> None:
    from .enhance.enhance_handlers import register_handlers as reg_enhance
    from .ingest.ingest_handlers import register_handlers as reg_ingest
    reg_ingest(runner)
    reg_enhance(runner)
