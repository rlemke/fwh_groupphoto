"""Storage for the groupphoto tools — local filesystem or S3/MinIO.

⚠️ A THIN SHIM over ``facetwork.domains.toolstorage``. This module and
fwh_sentinel2's were BYTE-IDENTICAL apart from the docstring and ``NAMESPACE``;
the implementation now lives once, in core.

Nothing about the behaviour changed: same path dispatch, same boto3 client, same
shared cache root, same recursive-relative ``list_files``, same atomic local
write. Conforms to agent-spec/cache-layout. S3 needs ``boto3``
(``pip install -e ".[s3]"``) and the standard ``FW_S3_*`` env, exactly like the
runtime.
"""
from __future__ import annotations

from facetwork.domains.toolstorage import tool_storage

NAMESPACE = "groupphoto"
_S = tool_storage(NAMESPACE)

LOCAL_DEFAULT_ROOT = _S.LOCAL_DEFAULT_ROOT
S3_DEFAULT_ROOT = _S.S3_DEFAULT_ROOT


def backend() -> str:
    return _S.backend()


def is_s3(path: str) -> bool:
    return _S.is_s3(path)


def data_root() -> str:
    return _S.data_root()


def cache_root() -> str:
    return _S.cache_root()


def output_root() -> str:
    return _S.output_root()


def join(*parts: str) -> str:
    return _S.join(*parts)


def exists(path: str) -> bool:
    return _S.exists(path)


def read_bytes(path: str) -> bytes:
    return _S.read_bytes(path)


def write_bytes(path: str, data: bytes) -> None:
    _S.write_bytes(path, data)


def read_text(path: str) -> str:
    return _S.read_text(path)


def write_text(path: str, text: str) -> None:
    _S.write_text(path, text)


def list_files(dir_path: str) -> list[str]:
    return _S.list_files(dir_path)
