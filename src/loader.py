"""
CSV loader: finds the right file for each source, standardizes columns,
applies config mappings, and normalizes MMU/operator names.
"""
import os
import glob
import logging
from typing import Dict, Any, Optional

import pandas as pd

from src.utils import standardize_column_name, standardize_columns, normalize_text
from src.quality import QualityCollector

logger = logging.getLogger(__name__)


def find_source_file(input_dir: str, filename_hint: str) -> Optional[str]:
    """
    Locate a CSV file in input_dir.
    First tries an exact filename match, then a case-insensitive glob.
    """
    if not filename_hint or filename_hint.startswith('FILL_IN_'):
        return None

    exact = os.path.join(input_dir, filename_hint)
    if os.path.exists(exact):
        return exact

    # Case-insensitive search across all CSVs
    all_csvs = glob.glob(os.path.join(input_dir, '*.csv'))
    needle = filename_hint.lower()
    for path in all_csvs:
        if os.path.basename(path).lower() == needle:
            return path

    logger.warning("Source file not found: %s (looked in %s)", filename_hint, input_dir)
    return None


def load_raw_csv(filepath: str) -> pd.DataFrame:
    """
    Read a CSV as all-string, standardize column names, and attach provenance columns.
    """
    try:
        df = pd.read_csv(filepath, dtype=str, skipinitialspace=True, encoding='utf-8-sig')
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, dtype=str, skipinitialspace=True, encoding='latin-1')

    # Preserve original column names before standardization (used by prestart parser)
    original_columns = list(df.columns)
    df = standardize_columns(df)
    df.attrs['col_name_map'] = dict(zip(df.columns, original_columns))

    df['_source_file'] = os.path.basename(filepath)
    df['_source_row_index'] = range(len(df))
    logger.info("Loaded %d rows from %s (%d columns)", len(df), os.path.basename(filepath), len(df.columns))
    return df


def apply_column_mapping(df: pd.DataFrame, column_map: Dict[str, Optional[str]]) -> pd.DataFrame:
    """
    Add canonical-named columns from the mapping.
    column_map: {canonical_name: 'Original Source Header'}
    The original header is standardized before lookup so the config can use
    natural header text ('Operator Name') or already-standardized ('operator_name').
    """
    result = df.copy()
    existing_std = set(df.columns)

    for canonical, original in column_map.items():
        if not original:
            continue
        std_original = standardize_column_name(original)
        if std_original in existing_std:
            result[canonical] = result[std_original]
            logger.debug("Mapped '%s' -> canonical '%s'", std_original, canonical)
        else:
            logger.debug(
                "Mapping '%s' (standardized: '%s') not found. Available: %s",
                original, std_original, list(df.columns[:10]),
            )
    return result


def load_source(
    source_name: str,
    config: Dict[str, Any],
    input_dir: str,
    quality: QualityCollector,
) -> pd.DataFrame:
    """
    Full load pipeline for one named source:
      find file → load CSV → apply column mapping → normalize aliases.
    Returns an empty DataFrame (with provenance columns) if the file is missing.
    """
    src_config = config.get('sources', {}).get(source_name) or {}
    filename = src_config.get('filename', '')
    column_map = src_config.get('columns') or {}

    filepath = find_source_file(input_dir, filename)
    if not filepath:
        logger.warning("Skipping source '%s': no file found (configured: '%s')", source_name, filename)
        return pd.DataFrame(columns=['_source_file', '_source_row_index'])

    df = load_raw_csv(filepath)
    df = apply_column_mapping(df, column_map)

    # Normalize MMU and operator names using alias tables
    mmu_aliases = config.get('mmu_aliases') or {}
    op_aliases = config.get('operator_aliases') or {}

    if 'mmu_id' in df.columns:
        df['mmu_id'] = df['mmu_id'].apply(lambda v: normalize_text(v, mmu_aliases))
    if 'operator_name' in df.columns:
        df['operator_name'] = df['operator_name'].apply(lambda v: normalize_text(v, op_aliases))

    df['_source_name'] = source_name
    return df
