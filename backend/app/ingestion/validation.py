"""File validation: extension, magic bytes, size, filename safety, macro rejection.

Nothing here parses the file's *business* content -- that is `parsing.py`'s job once a
file has passed every check in this module. This module's only job is deciding whether a
file is safe to even open.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

import magic

_ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
_REJECTED_MACRO_EXTENSIONS = {".xlsm", ".xlsb", ".xls"}
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,255}$")

_CSV_MIME_PREFIXES = ("text/plain", "text/csv", "application/csv")
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ZIP_MIME = "application/zip"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str | None
    detected_mime: str | None
    extension: str | None


def validate_filename(filename: str) -> str | None:
    """Returns a rejection reason, or None if the filename is safe."""
    if ".." in filename or "/" in filename or "\\" in filename:
        return "Filename must not contain path separators or '..'."
    if not _SAFE_FILENAME_RE.match(filename):
        return "Filename contains unsafe characters; only letters, digits, '.', '_', '-' are allowed."
    return None


def extension_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def validate_upload(*, filename: str, content: bytes, max_bytes: int, max_rows: int) -> ValidationResult:
    filename_problem = validate_filename(filename)
    if filename_problem:
        return ValidationResult(ok=False, reason=filename_problem, detected_mime=None, extension=None)

    extension = extension_of(filename)
    if extension in _REJECTED_MACRO_EXTENSIONS:
        return ValidationResult(
            ok=False,
            reason=f"'{extension}' files (macro-capable or legacy binary formats) are not accepted.",
            detected_mime=None,
            extension=extension,
        )
    if extension not in _ALLOWED_EXTENSIONS:
        return ValidationResult(
            ok=False,
            reason=f"Unsupported file extension '{extension}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}.",
            detected_mime=None,
            extension=extension,
        )

    if len(content) == 0:
        return ValidationResult(ok=False, reason="File is empty.", detected_mime=None, extension=extension)
    if len(content) > max_bytes:
        return ValidationResult(
            ok=False,
            reason=f"File size {len(content)} bytes exceeds the {max_bytes}-byte limit.",
            detected_mime=None,
            extension=extension,
        )

    detected_mime = magic.from_buffer(content, mime=True)
    if extension == ".csv" and not any(detected_mime.startswith(p) for p in _CSV_MIME_PREFIXES):
        return ValidationResult(
            ok=False,
            reason=f"File extension is .csv but detected content type is {detected_mime!r}.",
            detected_mime=detected_mime,
            extension=extension,
        )
    if extension == ".xlsx" and detected_mime not in (_XLSX_MIME, _ZIP_MIME):
        return ValidationResult(
            ok=False,
            reason=f"File extension is .xlsx but detected content type is {detected_mime!r}.",
            detected_mime=detected_mime,
            extension=extension,
        )

    row_count = content.count(b"\n")
    if extension == ".csv" and row_count > max_rows:
        return ValidationResult(
            ok=False,
            reason=f"File has approximately {row_count} rows, exceeding the {max_rows}-row limit.",
            detected_mime=detected_mime,
            extension=extension,
        )

    return ValidationResult(ok=True, reason=None, detected_mime=detected_mime, extension=extension)


def generate_stored_filename(extension: str) -> str:
    """A filesystem-safe, collision-proof name -- never derived from the user-supplied
    filename, which sidesteps path-traversal/overwrite risk entirely rather than just
    sanitising it."""
    return f"{uuid.uuid4().hex}{extension}"
