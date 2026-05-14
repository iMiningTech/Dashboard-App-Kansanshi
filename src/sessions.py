"""
Shift session builder.

Supports two shift_log formats:
  A) Event-per-row (Jotform style):
       Each row is a START or END event identified by a 'shift_event_type' column.
       Sessions are built by pairing START rows with their matching END rows.

  B) Session-per-row (legacy):
       Each row contains both shift_start_timestamp and shift_end_timestamp.

Format A is auto-detected when 'shift_event_type' is present after column mapping.
"""
import logging
from typing import Optional, Tuple

import pandas as pd

from src.utils import parse_timestamp_series, generate_session_id
from src.quality import QualityCollector

logger = logging.getLogger(__name__)

SESSION_COLUMNS = [
    'session_id',
    'mmu_id',
    'operator_name',
    'shift_start_timestamp',
    'shift_end_timestamp',
    'reporting_date',
    '_source_file',
    '_source_row_index',
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_sessions(
    shift_df: pd.DataFrame,
    config: dict,
    quality: QualityCollector,
) -> pd.DataFrame:
    """
    Build a sessions DataFrame from the shift_log source.
    Auto-detects event-per-row vs session-per-row format.
    """
    if shift_df.empty:
        logger.warning("shift_log is empty — no sessions will be created.")
        return pd.DataFrame(columns=SESSION_COLUMNS)

    if 'shift_event_type' in shift_df.columns:
        logger.info("shift_log: detected event-per-row format (START/END rows)")
        return _build_sessions_from_events(shift_df, config, quality)
    else:
        logger.info("shift_log: detected session-per-row format")
        return _build_sessions_from_pairs(shift_df, config, quality)


# ---------------------------------------------------------------------------
# Format A — event-per-row (Jotform START/END rows)
# ---------------------------------------------------------------------------

def _build_sessions_from_events(
    shift_df: pd.DataFrame,
    config: dict,
    quality: QualityCollector,
) -> pd.DataFrame:
    """
    Pair START and END event rows into sessions.

    Matching rules:
      1. Same mmu_id
      2. END timestamp is after START timestamp
      3. Prefer same calendar date
      4. Take the earliest valid END to avoid crossing into the next shift
    """
    tz = config['settings'].get('timezone')
    src_cfg = (config.get('sources') or {}).get('shift_log') or {}
    start_values = set(v.upper() for v in (src_cfg.get('start_values') or ['START']))
    end_values = set(v.upper() for v in (src_cfg.get('end_values') or ['END']))

    df = shift_df.copy()

    # Parse timestamp column; fall back to shift_start_timestamp if mapped that way
    ts_col = 'timestamp' if 'timestamp' in df.columns else 'shift_start_timestamp'
    df['_parsed_ts'] = parse_timestamp_series(df[ts_col].fillna(''), tz)
    df['_event_upper'] = df['shift_event_type'].fillna('').str.strip().str.upper()

    starts = df[df['_event_upper'].isin(start_values)].copy()
    ends = df[df['_event_upper'].isin(end_values)].copy()

    used_end_indices: set = set()
    sessions = []

    for _, start_row in starts.iterrows():
        mmu = str(start_row.get('mmu_id', '') or '').strip()
        operator = str(start_row.get('operator_name', '') or '').strip()
        start_ts = start_row['_parsed_ts']

        # Quality checks on the START row
        if not mmu:
            quality.add_from_row(start_row, 'Missing mmu_id on Shift Start', 'shift_log', 'mmu_id')
        if not operator:
            quality.add_from_row(start_row, 'Missing operator_name on Shift Start', 'shift_log', 'operator_name')
        if pd.isna(start_ts):
            quality.add_from_row(start_row, 'Missing/unparseable timestamp on Shift Start', 'shift_log', 'timestamp')

        end_ts = _find_matching_end(mmu, start_ts, ends, used_end_indices, quality)

        date_str = str(start_ts.date()) if pd.notna(start_ts) else 'NODATE'
        session_id = generate_session_id(len(sessions) + 1, mmu, date_str, operator)

        sessions.append({
            'session_id': session_id,
            'mmu_id': mmu or None,
            'operator_name': operator or None,
            'shift_start_timestamp': start_ts,
            'shift_end_timestamp': end_ts,
            'reporting_date': date_str if date_str != 'NODATE' else None,
            '_source_file': start_row.get('_source_file', ''),
            '_source_row_index': start_row.get('_source_row_index'),
        })

    # Flag unmatched END rows
    for idx, end_row in ends.iterrows():
        if idx not in used_end_indices:
            quality.add(
                reason='Shift End row has no matching Shift Start',
                source_table='shift_log',
                source_file=str(end_row.get('_source_file', '')),
                source_row_index=end_row.get('_source_row_index'),
                mmu_id=str(end_row.get('mmu_id', '')),
                operator_name=str(end_row.get('operator_name', '')),
                timestamp=str(end_row['_parsed_ts']),
            )

    if not sessions:
        return pd.DataFrame(columns=SESSION_COLUMNS)

    result = pd.DataFrame(sessions)
    logger.info("Built %d sessions from %d START rows (%d END rows)", len(sessions), len(starts), len(ends))
    return result


def _find_matching_end(
    mmu: str,
    start_ts: pd.Timestamp,
    ends: pd.DataFrame,
    used_end_indices: set,
    quality: QualityCollector,
) -> pd.Timestamp:
    """
    Find the best unused END row for a given START.
    Returns pd.NaT if no match is found.
    """
    candidates = ends[
        (ends.get('mmu_id', pd.Series(dtype=str)).fillna('').str.strip() == mmu)
        & (~ends.index.isin(used_end_indices))
    ]

    if candidates.empty:
        if mmu:
            quality.add(
                reason='No Shift End found for this MMU on this date',
                source_table='shift_log',
                mmu_id=mmu,
                timestamp=str(start_ts),
            )
        return pd.NaT

    # Prefer ENDs after START on the same date
    if pd.notna(start_ts):
        start_date = start_ts.date()

        same_date_after = candidates[
            candidates['_parsed_ts'].apply(
                lambda t: pd.notna(t) and t.date() == start_date and t > start_ts
            )
        ]

        if not same_date_after.empty:
            best_idx = same_date_after['_parsed_ts'].idxmin()
            used_end_indices.add(best_idx)
            return same_date_after.loc[best_idx, '_parsed_ts']

        # Fallback: any END after START (next day shift crossover)
        any_after = candidates[
            candidates['_parsed_ts'].apply(lambda t: pd.notna(t) and t > start_ts)
        ]
        if not any_after.empty:
            best_idx = any_after['_parsed_ts'].idxmin()
            used_end_indices.add(best_idx)
            return any_after.loc[best_idx, '_parsed_ts']

    quality.add(
        reason='No Shift End found after Shift Start timestamp',
        source_table='shift_log',
        mmu_id=mmu,
        timestamp=str(start_ts),
    )
    return pd.NaT


# ---------------------------------------------------------------------------
# Format B — session-per-row (one row = full session with start + end cols)
# ---------------------------------------------------------------------------

def _build_sessions_from_pairs(
    shift_df: pd.DataFrame,
    config: dict,
    quality: QualityCollector,
) -> pd.DataFrame:
    """Build sessions where each row already contains shift_start and shift_end."""
    tz = config['settings'].get('timezone')
    rows = []

    for _, row in shift_df.iterrows():
        mmu = str(row.get('mmu_id', '') or '').strip()
        operator = str(row.get('operator_name', '') or '').strip()
        t_start = parse_timestamp_series(pd.Series([row.get('shift_start_timestamp', '')]), tz).iloc[0]
        t_end = parse_timestamp_series(pd.Series([row.get('shift_end_timestamp', '')]), tz).iloc[0]

        if not mmu:
            quality.add_from_row(row, 'Missing mmu_id', 'shift_log', 'mmu_id')
        if not operator:
            quality.add_from_row(row, 'Missing operator_name', 'shift_log', 'operator_name')
        if pd.isna(t_start):
            quality.add_from_row(row, 'Missing/unparseable shift_start_timestamp', 'shift_log', 'shift_start_timestamp')
        if pd.isna(t_end):
            quality.add_from_row(row, 'Missing/unparseable shift_end_timestamp', 'shift_log', 'shift_end_timestamp')

        date_str = str(t_start.date()) if pd.notna(t_start) else 'NODATE'
        session_id = generate_session_id(len(rows) + 1, mmu, date_str, operator)

        rows.append({
            'session_id': session_id,
            'mmu_id': mmu or None,
            'operator_name': operator or None,
            'shift_start_timestamp': t_start,
            'shift_end_timestamp': t_end,
            'reporting_date': date_str if date_str != 'NODATE' else None,
            '_source_file': row.get('_source_file', ''),
            '_source_row_index': row.get('_source_row_index'),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=SESSION_COLUMNS)


# ---------------------------------------------------------------------------
# Session matching (used by timeline builder)
# ---------------------------------------------------------------------------

def match_event_to_session(
    mmu_id: Optional[str],
    timestamp: pd.Timestamp,
    reporting_date: Optional[str],
    sessions: pd.DataFrame,
) -> Tuple[Optional[str], str]:
    """
    Find the best session for an event (mmu_id + timestamp).

    Returns (session_id, match_method) where match_method is:
        'window'        — timestamp falls inside shift window
        'date_fallback' — same mmu + same date (no window match)
        'none'          — no match found
    """
    if sessions.empty or not mmu_id:
        return None, 'none'

    candidates = sessions[sessions['mmu_id'] == mmu_id]
    if candidates.empty:
        return None, 'none'

    # Primary: timestamp inside shift window
    if pd.notna(timestamp):
        in_window = candidates[
            candidates['shift_start_timestamp'].notna()
            & candidates['shift_end_timestamp'].notna()
            & (timestamp >= candidates['shift_start_timestamp'])
            & (timestamp <= candidates['shift_end_timestamp'])
        ]
        if len(in_window) == 1:
            return in_window.iloc[0]['session_id'], 'window'
        if len(in_window) > 1:
            diffs = (timestamp - in_window['shift_start_timestamp']).abs()
            best = in_window.loc[diffs.idxmin()]
            return best['session_id'], 'window'

    # Fallback: same date
    event_date = (
        str(timestamp.date()) if pd.notna(timestamp)
        else reporting_date
    )
    if event_date:
        same_date = candidates[candidates['reporting_date'] == event_date]
        if not same_date.empty:
            return same_date.iloc[0]['session_id'], 'date_fallback'

    return None, 'none'
