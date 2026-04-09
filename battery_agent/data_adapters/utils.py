"""Utility functions for data adapters."""

import csv
import re
from typing import Any

import pandas as pd


def normalize_adapter_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or None


def _clean_header_cell(value: Any) -> str:
    return str(value or "").replace("\ufeff", "").replace("\t", "").strip().strip('"')


def _normalize_header_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_header_cell(value).lower())


def _coerce_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _parse_duration_series_to_seconds(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(dtype="float64")

    numeric = pd.to_numeric(series, errors="coerce")
    normalized_text = series.astype(str).str.strip()
    timedelta_mask = numeric.isna() & normalized_text.ne("") & normalized_text.ne("nan")
    parsed = numeric.astype("float64")

    if timedelta_mask.any():
        timedeltas = pd.to_timedelta(normalized_text[timedelta_mask], errors="coerce")
        parsed.loc[timedelta_mask] = timedeltas.dt.total_seconds()

    return parsed.astype("float64")


def extract_raw_header_candidates(text: str) -> list[str]:
    lines = [line for line in text.splitlines() if line.strip()]
    discovered: list[str] = []
    seen: set[str] = set()
    for line in lines[:3]:
        for cell in next(csv.reader([line]), []):
            cleaned = _clean_header_cell(cell)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            discovered.append(cleaned)
    return discovered
