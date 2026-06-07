"""
Shared utility functions: column name standardization, timestamp parsing,
name/MMU normalization, and session ID generation.
"""
import re
import logging
from datetime import datetime
from typing import Optional, Dict

import pandas as pd

logger = logging.getLogger(__name__)

# Try these formats explicitly when pandas auto-detect fails
_EXTRA_TIMESTAMP_FORMATS = [
    '%d/%m/%Y %H:%M:%S',
    '%d/%m/%Y %H:%M',
    '%m/%d/%Y %H:%M:%S',
    '%m/%d/%Y %H:%M',
    '%d-%m-%Y %H:%M:%S',
    '%d-%m-%Y %H:%M',
    '%Y/%m/%d %H:%M:%S',
    '%Y/%m/%d %H:%M',
    '%d/%m/%Y',
    '%Y-%m-%d',
]


def standardize_column_name(col: str) -> str:
    """
    Convert any column header to lowercase_underscore format.
    e.g. 'Operator Name' -> 'operator_name', 'MMU #' -> 'mmu_'
    """
    col = str(col).strip().lower()
    col = re.sub(r'[^a-z0-9]+', '_', col)
    col = re.sub(r'_+', '_', col)
    col = col.strip('_')
    return col


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Apply standardize_column_name to every column in the DataFrame."""
    df = df.copy()
    df.columns = [standardize_column_name(c) for c in df.columns]
    return df


def parse_timestamp(value, timezone: Optional[str] = None) -> pd.Timestamp:
    """
    Robustly parse a single timestamp value into a pd.Timestamp.
    Returns pd.NaT on failure.
    """
    if pd.isna(value) or str(value).strip() == '':
        return pd.NaT

    val_str = str(value).strip()

    # ISO dates (YYYY-MM-DD…) must NOT use dayfirst: pandas would read them as
    # YYYY-DD-MM and swap month/day (e.g. "2026-06-07" -> 6 July). dayfirst is
    # only for ambiguous day-first strings like "07/06/2026" (legacy CSV exports).
    iso_like = bool(re.match(r"^\d{4}-\d{2}-\d{2}", val_str))
    try:
        ts = pd.to_datetime(val_str, dayfirst=not iso_like)
        if timezone:
            ts = ts.tz_localize(timezone) if ts.tzinfo is None else ts.tz_convert(timezone)
        return ts
    except Exception:
        pass

    # Fall back to explicit format list
    for fmt in _EXTRA_TIMESTAMP_FORMATS:
        try:
            ts = pd.Timestamp(datetime.strptime(val_str, fmt))
            if timezone:
                ts = ts.tz_localize(timezone)
            return ts
        except ValueError:
            continue

    logger.warning("Could not parse timestamp: %r", value)
    return pd.NaT


def parse_timestamp_series(series: pd.Series, timezone: Optional[str] = None) -> pd.Series:
    """Parse an entire Series of timestamp strings."""
    return series.apply(lambda v: parse_timestamp(v, timezone))


def normalize_text(value, aliases: Dict[str, str]) -> str:
    """
    Look up a value in an alias dict (case-insensitive).
    Returns the canonical form if found, otherwise the stripped original.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return value
    s = str(value).strip()
    if not s:
        return s
    # Exact match first
    if s in aliases:
        return aliases[s]
    # Case-insensitive fallback
    s_lower = s.lower()
    for k, v in aliases.items():
        if str(k).strip().lower() == s_lower:
            return v
    return s


def generate_session_id(index: int, mmu_id, date_str: str, operator: str) -> str:
    """
    Build a human-readable, sortable session ID.
    e.g. S0001_20240115_MMU003_John
    """
    mmu_clean = re.sub(r'[^a-zA-Z0-9]', '', str(mmu_id or 'UNK'))[:8]
    date_clean = str(date_str or 'NODATE').replace('-', '')[:8]
    op_first = str(operator or 'UNK').strip().split()[0] if (operator and str(operator).strip()) else 'UNK'
    op_clean = re.sub(r'[^a-zA-Z0-9]', '', op_first)[:6]
    return f"S{index:04d}_{date_clean}_{mmu_clean}_{op_clean}"
