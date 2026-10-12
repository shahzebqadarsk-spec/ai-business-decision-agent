"""Raw uploaded-file storage -- deliberately separate from canonical business tables.

Raw files live on disk under `UPLOAD_STORAGE_PATH`, named by `generate_stored_filename()`
(never by the user-supplied filename). The database only ever stores the path and a
SHA-256 digest, never the bytes themselves.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def store_upload(*, storage_root: Path, stored_filename: str, content: bytes) -> Path:
    storage_root.mkdir(parents=True, exist_ok=True)
    destination = storage_root / stored_filename
    destination.write_bytes(content)
    return destination
