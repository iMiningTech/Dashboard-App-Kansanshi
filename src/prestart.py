"""
Pre-start checklist normalizer.

Converts Jotform MMU Pre-Start forms from wide format to long format.

Jotform pre-start columns follow this triplicate pattern:
  "CATEGORY >> ITEM DESCRIPTION >> STATUS"
  "CATEGORY >> ITEM DESCRIPTION >> FAULT NO."
  "CATEGORY >> ITEM DESCRIPTION >> Comment"

This module auto-detects groups by finding columns whose standardized name
ends with '_status' and then locates the paired fault and comment columns.
Original column names are recovered from df.attrs['col_name_map'] so that
output labels remain human-readable.

Output: one row per (MMU, date, checklist item)
"""
import logging
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.utils import parse_timestamp_series
from src.quality import QualityCollector

logger = logging.getLogger(__name__)

PRESTART_COLUMNS = [
    'mmu_id',
    'operator_name',
    'inspection_timestamp',
    'reporting_date',
    'checklist_category',
    'checklist_item',
    'status',
    'fault_number',
    'comment',
    'fault_flag',
    'source_row_index',
    'source_file',
]

# Metadata / system columns that are never checklist items
_SYSTEM_SUFFIXES = {
    '_status', '_fault_no_', '_fault_no', '_comment',
    '_comments', '_photo_optional_', '_photo_optional',
}
_SYSTEM_KEYWORDS = {
    'submission_date', 'submission_ip', 'submission_id',
    'device_id', 'signature', 'plant_', 'source_app',
    'kilometers', 'engine_hours', 'fleet_no_', 'full_name', 'date',
}


# ---------------------------------------------------------------------------
# Column group detection
# ---------------------------------------------------------------------------

ChecklistGroup = Dict  # {base_std, base_original, category, item_name, status_col, fault_col, comment_col}


def _detect_checklist_groups(df: pd.DataFrame) -> List[ChecklistGroup]:
    """
    Identify STATUS/FAULT/Comment column triples.

    Works on standardized column names; recovers human-readable originals
    from df.attrs['col_name_map'] if available.
    """
    col_name_map: Dict[str, str] = df.attrs.get('col_name_map', {})
    std_cols = set(df.columns)
    groups = []
    seen_bases: set = set()

    for col in df.columns:
        if not col.endswith('_status'):
            continue
        # Strip _status to get the base prefix
        base_std = col[: -len('_status')]
        if base_std in seen_bases:
            continue
        # Skip if the base is empty or looks like a system field
        if not base_std or any(kw in base_std for kw in _SYSTEM_KEYWORDS):
            continue
        seen_bases.add(base_std)

        # Find matching fault and comment columns by prefix
        fault_col = _find_col(base_std, ['_fault_no_', '_fault_no', '_fault'], std_cols)
        comment_col = _find_col(base_std, ['_comment', '_comments'], std_cols)

        # Recover human-readable original column name for the base
        original_status = col_name_map.get(col, col)
        category, item_name = _parse_original_label(original_status)

        groups.append({
            'base_std': base_std,
            'category': category,
            'item_name': item_name,
            'status_col': col,
            'fault_col': fault_col,
            'comment_col': comment_col,
        })

    logger.debug("Detected %d checklist item groups", len(groups))
    return groups


def _find_col(base: str, suffixes: List[str], std_cols: set) -> Optional[str]:
    """Return the first column matching base + any of the given suffixes."""
    for suffix in suffixes:
        candidate = base + suffix
        if candidate in std_cols:
            return candidate
    return None


def _parse_original_label(original_col: str) -> Tuple[str, str]:
    """
    Parse "CATEGORY >> ITEM >> STATUS" into (category, item_name).
    Returns ('', original_col) if the pattern is not found.
    """
    # Strip the trailing >> STATUS / >> FAULT NO. / >> Comment
    label = re.sub(r'\s*>>\s*(STATUS|FAULT NO\.|FAULT NO|Comment|Comments)\s*$', '',
                   original_col, flags=re.IGNORECASE).strip()
    parts = [p.strip() for p in label.split('>>')]
    if len(parts) >= 2:
        return parts[0], ' >> '.join(parts[1:])
    return '', label


# ---------------------------------------------------------------------------
# Main normalizer
# ---------------------------------------------------------------------------

def normalize_prestart(
    prestart_df: pd.DataFrame,
    config: dict,
    quality: QualityCollector,
) -> pd.DataFrame:
    """
    Main entry point. Returns long-format DataFrame with one row per item per inspection.
    """
    if prestart_df.empty:
        logger.warning("prestart_checklist is empty — skipping.")
        return pd.DataFrame(columns=PRESTART_COLUMNS)

    tz = config['settings'].get('timezone')
    fault_keywords = [kw.lower() for kw in (config.get('fault_keywords') or [])]

    # Detect triplicate groups
    groups = _detect_checklist_groups(prestart_df)

    # Also respect any explicitly listed checklist_item_columns in config
    src_config = (config.get('sources') or {}).get('prestart_checklist') or {}
    explicit_cols: List[str] = src_config.get('checklist_item_columns') or []
    if explicit_cols and not groups:
        # Fallback: treat each listed column as a flat status-only item
        groups = [
            {'base_std': c, 'category': '', 'item_name': c,
             'status_col': c, 'fault_col': None, 'comment_col': None}
            for c in explicit_cols if c in prestart_df.columns
        ]

    if not groups:
        logger.warning(
            "No checklist item columns detected in pre-start CSV. "
            "Check that the CSV uses '>> STATUS' column naming or set "
            "'checklist_item_columns' in config/mappings.yaml."
        )

    rows = []

    for _, row in prestart_df.iterrows():
        mmu = str(row.get('mmu_id', '') or '').strip() or None
        operator = str(row.get('operator_name', '') or '').strip() or None
        raw_ts = row.get('inspection_timestamp', '')
        ts = parse_timestamp_series(pd.Series([raw_ts]), tz).iloc[0]
        source_row = row.get('_source_row_index')
        source_file = str(row.get('_source_file', '') or '')

        reporting_date = (
            str(ts.date()) if pd.notna(ts)
            else str(row.get('reporting_date', '') or '')
        )

        # Quality checks
        if not mmu:
            quality.add_from_row(row, 'Missing mmu_id', 'prestart_checklist', 'mmu_id')
        if pd.isna(ts):
            quality.add_from_row(
                row, 'Missing/unparseable inspection_timestamp',
                'prestart_checklist', 'inspection_timestamp',
            )

        if groups:
            for grp in groups:
                status = str(row.get(grp['status_col'], '') or '').strip()
                fault_number = str(row.get(grp['fault_col'], '') or '').strip() if grp['fault_col'] else ''
                comment = str(row.get(grp['comment_col'], '') or '').strip() if grp['comment_col'] else ''
                fault_flag = _is_fault(status, fault_keywords)

                rows.append({
                    'mmu_id': mmu,
                    'operator_name': operator,
                    'inspection_timestamp': ts,
                    'reporting_date': reporting_date,
                    'checklist_category': grp['category'],
                    'checklist_item': grp['item_name'],
                    'status': status,
                    'fault_number': fault_number,
                    'comment': comment,
                    'fault_flag': fault_flag,
                    'source_row_index': source_row,
                    'source_file': source_file,
                })
        else:
            # Emit a placeholder row so the inspection record is not silently dropped
            rows.append({
                'mmu_id': mmu,
                'operator_name': operator,
                'inspection_timestamp': ts,
                'reporting_date': reporting_date,
                'checklist_category': '(no items detected)',
                'checklist_item': '(no items detected)',
                'status': '',
                'fault_number': '',
                'comment': '',
                'fault_flag': False,
                'source_row_index': source_row,
                'source_file': source_file,
            })

    df = pd.DataFrame(rows, columns=PRESTART_COLUMNS)
    n_inspections = len(prestart_df)
    n_faults = df['fault_flag'].sum()
    logger.info(
        "Pre-start report: %d rows from %d inspections (%d fault flags)",
        len(df), n_inspections, n_faults,
    )
    return df


def _is_fault(response: str, fault_keywords: List[str]) -> bool:
    if not response:
        return False
    r = response.lower().strip()
    return any(kw in r for kw in fault_keywords)
