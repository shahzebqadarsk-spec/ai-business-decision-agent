from __future__ import annotations

from app.ingestion.validation import (
    extension_of,
    generate_stored_filename,
    validate_filename,
    validate_upload,
)

_SMALL_CSV = b"a,b,c\n1,2,3\n4,5,6\n"


def test_valid_csv_passes() -> None:
    result = validate_upload(filename="sales.csv", content=_SMALL_CSV, max_bytes=1_000_000, max_rows=1000)
    assert result.ok
    assert result.extension == ".csv"


def test_rejects_unsafe_filename_with_path_traversal() -> None:
    result = validate_upload(
        filename="../../etc/passwd.csv", content=_SMALL_CSV, max_bytes=1_000_000, max_rows=1000
    )
    assert not result.ok
    assert "path separators" in (result.reason or "") or "unsafe" in (result.reason or "")


def test_rejects_unsupported_extension() -> None:
    result = validate_upload(filename="script.exe", content=_SMALL_CSV, max_bytes=1_000_000, max_rows=1000)
    assert not result.ok
    assert "extension" in (result.reason or "")


def test_rejects_macro_capable_extension() -> None:
    result = validate_upload(filename="book.xlsm", content=_SMALL_CSV, max_bytes=1_000_000, max_rows=1000)
    assert not result.ok
    assert "macro" in (result.reason or "").lower()


def test_rejects_file_over_size_limit() -> None:
    result = validate_upload(filename="big.csv", content=_SMALL_CSV, max_bytes=5, max_rows=1000)
    assert not result.ok
    assert "size" in (result.reason or "")


def test_rejects_file_over_row_limit() -> None:
    content = b"a,b\n" + b"1,2\n" * 2000
    result = validate_upload(filename="many_rows.csv", content=content, max_bytes=1_000_000, max_rows=100)
    assert not result.ok
    assert "row" in (result.reason or "")


def test_rejects_content_mismatched_with_extension() -> None:
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    result = validate_upload(filename="fake.csv", content=png_header, max_bytes=1_000_000, max_rows=1000)
    assert not result.ok
    assert "content type" in (result.reason or "")


def test_rejects_empty_file() -> None:
    result = validate_upload(filename="empty.csv", content=b"", max_bytes=1_000_000, max_rows=1000)
    assert not result.ok


def test_valid_filename_has_no_rejection_reason() -> None:
    assert validate_filename("sales_2025.csv") is None


def test_stored_filename_is_never_derived_from_user_input() -> None:
    stored = generate_stored_filename(".csv")
    assert stored != "sales.csv"
    assert stored.endswith(".csv")
    assert len(stored) > 10


def test_extension_of() -> None:
    assert extension_of("a.b.CSV") == ".csv"
    assert extension_of("noextension") == ""
