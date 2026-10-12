"""Turns a validated raw file into a pandas DataFrame of strings (dtype inference happens
explicitly in profiling.py, not implicitly in the parser) plus a row count.

Deliberately dumb: no business-logic interpretation of columns happens here. Reads the
file as text by default so a malformed value can't silently become NaN/0 before
data-quality checks get a chance to see it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_upload(path: Path, *, extension: str, max_rows: int) -> pd.DataFrame:
    if extension == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=True, nrows=max_rows + 1)
    elif extension == ".xlsx":
        df = pd.read_excel(path, dtype=str, nrows=max_rows + 1)
    else:
        raise ValueError(f"Unsupported extension for parsing: {extension!r}")

    if len(df) > max_rows:
        raise ValueError(f"File has more than {max_rows} data rows.")
    return df
