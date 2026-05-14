"""
Activity timeline builder.

Merges events from shift sessions, event_log, and toolbox_talk into a single
chronological table, matches events to sessions, calculates durations, and
flags data quality issues.

Timeline event ordering within a session:
  Shift Start → (events sorted by timestamp) → Shift End
"""
import logging
from typing import Optional

import pandas as pd

from src.utils import parse_timestamp_series
from src.sessions import match_event_to_session
from src.quality import QualityCollector

logger = logging.getLogger(__name__)

# Canonical columns for the output timeline
TIMELINE_COLUMNS = [
    'session_id',
    'mmu_id',
    'operator_name',
    'source_table',
    'activity_type',
    'activity_category',
    'activity_detail',
    'start_timestamp',
    'end_timestamp',
    'duration_minutes',
    'reporting_date',
    'shift_start_timestamp',
    'shift_end_timestamp',
    'session_match_method',
    'is_exception',
    'exception_reason',
]


# ---------------------------------------------------------------------------
# Event factories
# ---------------------------------------------------------------------------

def _session_boundary_events(sessions: pd.DataFrame) -> pd.DataFrame:
    """
    Synthesize Shift Start and Shift End activity rows for every session.
    """
    rows = []
    for _, s in sessions.iterrows():
        base = {
            'session_id': s['session_id'],
            'mmu_id': s['mmu_id'],
            'operator_name': s['operator_name'],
            'shift_start_timestamp': s['shift_start_timestamp'],
            'shift_end_timestamp': s['shift_end_timestamp'],
            'reporting_date': s['reporting_date'],
            'session_match_method': 'session',
            'is_exception': False,
            'exception_reason': '',
        }
        rows.append({**base, 'activity_type': 'Shift Start', 'start_timestamp': s['shift_start_timestamp'],
                     'source_table': 'shift_log', 'activity_category': 'Shift', 'activity_detail': ''})
        if pd.notna(s['shift_end_timestamp']):
            rows.append({**base, 'activity_type': 'Shift End', 'start_timestamp': s['shift_end_timestamp'],
                         'source_table': 'shift_log', 'activity_category': 'Shift', 'activity_detail': ''})
    return pd.DataFrame(rows)


def _event_log_events(event_df: pd.DataFrame, sessions: pd.DataFrame, config: dict, quality: QualityCollector) -> pd.DataFrame:
    """Convert event_log rows into timeline events, matching each to a session."""
    if event_df.empty:
        return pd.DataFrame()

    tz = config['settings'].get('timezone')
    rows = []

    for _, row in event_df.iterrows():
        mmu = str(row.get('mmu_id', '') or '').strip() or None
        operator = str(row.get('operator_name', '') or '').strip() or None
        ts = parse_timestamp_series(pd.Series([row.get('timestamp', '')]), tz).iloc[0]
        activity_type = str(row.get('activity_type', '') or '').strip()
        activity_category = str(row.get('activity_category', '') or '').strip()
        activity_detail = str(row.get('activity_detail', '') or '').strip()
        reporting_date = str(row.get('reporting_date', '') or '').strip() or None

        exceptions = []
        if not mmu:
            exceptions.append('Missing mmu_id')
            quality.add_from_row(row, 'Missing mmu_id', 'event_log', 'mmu_id')
        if pd.isna(ts):
            exceptions.append('Missing or unparseable timestamp')
            quality.add_from_row(row, 'Missing/unparseable timestamp', 'event_log', 'timestamp')

        if reporting_date is None and pd.notna(ts):
            reporting_date = str(ts.date())

        session_id, match_method = match_event_to_session(mmu, ts, reporting_date, sessions)

        if session_id is None:
            exceptions.append('No matching shift session')
            quality.add_from_row(row, 'No matching shift session', 'event_log')
            # Attempt to get shift context from sessions with same mmu+date
            shift_start = shift_end = None
        else:
            s_row = sessions[sessions['session_id'] == session_id].iloc[0]
            shift_start = s_row['shift_start_timestamp']
            shift_end = s_row['shift_end_timestamp']
            matched_op = s_row['operator_name']
            if not operator:
                operator = matched_op  # inherit from session

        rows.append({
            'session_id': session_id,
            'mmu_id': mmu,
            'operator_name': operator,
            'source_table': 'event_log',
            'activity_type': activity_type or 'Unknown',
            'activity_category': activity_category,
            'activity_detail': activity_detail,
            'start_timestamp': ts,
            'end_timestamp': pd.NaT,
            'duration_minutes': None,
            'reporting_date': reporting_date,
            'shift_start_timestamp': shift_start if session_id else None,
            'shift_end_timestamp': shift_end if session_id else None,
            'session_match_method': match_method,
            'is_exception': bool(exceptions),
            'exception_reason': '; '.join(exceptions),
        })

    return pd.DataFrame(rows)


def _toolbox_talk_events(toolbox_df: pd.DataFrame, sessions: pd.DataFrame, config: dict, quality: QualityCollector) -> pd.DataFrame:
    """Convert toolbox_talk rows into 'Toolbox Talk' activity events."""
    if toolbox_df.empty:
        return pd.DataFrame()

    tz = config['settings'].get('timezone')
    rows = []

    for _, row in toolbox_df.iterrows():
        mmu = str(row.get('mmu_id', '') or '').strip() or None
        operator = str(row.get('operator_name', '') or '').strip() or None
        ts = parse_timestamp_series(pd.Series([row.get('timestamp', '')]), tz).iloc[0]
        reporting_date = str(row.get('reporting_date', '') or '').strip() or None

        exceptions = []
        if not mmu:
            exceptions.append('Missing mmu_id')
            quality.add_from_row(row, 'Missing mmu_id', 'toolbox_talk', 'mmu_id')
        if pd.isna(ts):
            exceptions.append('Missing or unparseable timestamp')
            quality.add_from_row(row, 'Missing/unparseable timestamp', 'toolbox_talk', 'timestamp')

        if reporting_date is None and pd.notna(ts):
            reporting_date = str(ts.date())

        session_id, match_method = match_event_to_session(mmu, ts, reporting_date, sessions)

        if session_id is None:
            exceptions.append('No matching shift session')
            quality.add_from_row(row, 'No matching shift session', 'toolbox_talk')
            shift_start = shift_end = None
        else:
            s_row = sessions[sessions['session_id'] == session_id].iloc[0]
            shift_start = s_row['shift_start_timestamp']
            shift_end = s_row['shift_end_timestamp']
            if not operator:
                operator = s_row['operator_name']

        rows.append({
            'session_id': session_id,
            'mmu_id': mmu,
            'operator_name': operator,
            'source_table': 'toolbox_talk',
            'activity_type': 'Toolbox Talk',
            'activity_category': 'Safety',
            'activity_detail': '',
            'start_timestamp': ts,
            'end_timestamp': pd.NaT,
            'duration_minutes': None,
            'reporting_date': reporting_date,
            'shift_start_timestamp': shift_start if session_id else None,
            'shift_end_timestamp': shift_end if session_id else None,
            'session_match_method': match_method,
            'is_exception': bool(exceptions),
            'exception_reason': '; '.join(exceptions),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Timeline assembly
# ---------------------------------------------------------------------------

def build_timeline(
    sessions: pd.DataFrame,
    event_df: pd.DataFrame,
    toolbox_df: pd.DataFrame,
    config: dict,
    quality: QualityCollector,
) -> pd.DataFrame:
    """
    Combine all event sources into one sorted timeline.
    """
    parts = [
        _session_boundary_events(sessions),
        _event_log_events(event_df, sessions, config, quality),
        _toolbox_talk_events(toolbox_df, sessions, config, quality),
    ]
    parts = [p for p in parts if not p.empty]

    if not parts:
        logger.warning("No timeline events produced.")
        return pd.DataFrame(columns=TIMELINE_COLUMNS)

    timeline = pd.concat(parts, ignore_index=True)

    # Ensure all expected columns exist
    for col in TIMELINE_COLUMNS:
        if col not in timeline.columns:
            timeline[col] = None

    # Sort: session → mmu → timestamp (NaT rows go last)
    timeline = timeline.sort_values(
        ['session_id', 'mmu_id', 'start_timestamp'],
        na_position='last',
    ).reset_index(drop=True)

    logger.info("Timeline assembled: %d rows", len(timeline))
    return timeline


# ---------------------------------------------------------------------------
# Duration calculation
# ---------------------------------------------------------------------------

def calculate_durations(
    timeline: pd.DataFrame,
    config: dict,
    quality: QualityCollector,
) -> pd.DataFrame:
    """
    Fill end_timestamp and duration_minutes for each event within its session.

    Rules:
    - duration = next event's start_timestamp − this event's start_timestamp
    - Last event in session:
        * If activity_type == 'Shift End': duration = 0, end = start
        * Otherwise: cap at max_activity_duration_minutes, flag exception
    - Negative durations (duplicate/out-of-order timestamps): flag, set to 0
    """
    max_dur = config['settings'].get('max_activity_duration_minutes', 240)
    default_shift_end = config['settings'].get('default_shift_end_if_missing')

    result = timeline.copy()

    grouped = result.groupby('session_id', sort=False)

    for session_id, group in grouped:
        idxs = group.index.tolist()
        n = len(idxs)

        for rank, idx in enumerate(idxs):
            activity_type = result.at[idx, 'activity_type']
            start = result.at[idx, 'start_timestamp']
            shift_end = result.at[idx, 'shift_end_timestamp']

            # Last event in session
            if rank == n - 1:
                if activity_type == 'Shift End':
                    result.at[idx, 'end_timestamp'] = start
                    result.at[idx, 'duration_minutes'] = 0.0
                else:
                    # No Shift End logged — use default or cap
                    if pd.notna(shift_end) and pd.notna(start):
                        raw_dur = (shift_end - start).total_seconds() / 60
                    elif default_shift_end and pd.notna(start):
                        # default_shift_end is a time string like "17:00"
                        try:
                            date_part = start.date()
                            t_hour, t_min = [int(x) for x in str(default_shift_end).split(':')]
                            shift_end_default = pd.Timestamp(
                                year=date_part.year, month=date_part.month, day=date_part.day,
                                hour=t_hour, minute=t_min,
                            )
                            raw_dur = (shift_end_default - start).total_seconds() / 60
                        except Exception:
                            raw_dur = max_dur
                    else:
                        raw_dur = max_dur

                    capped = min(max(raw_dur, 0), max_dur)
                    result.at[idx, 'duration_minutes'] = capped

                    exc_parts = []
                    if activity_type != 'Shift End':
                        exc_parts.append('Missing Shift End — duration capped')
                    if raw_dur > max_dur:
                        exc_parts.append(f'Duration {raw_dur:.0f} min exceeds threshold {max_dur} min')

                    if exc_parts:
                        result.at[idx, 'is_exception'] = True
                        existing = str(result.at[idx, 'exception_reason'] or '')
                        result.at[idx, 'exception_reason'] = '; '.join(filter(None, [existing] + exc_parts))
                        quality.add(
                            reason='; '.join(exc_parts),
                            source_table=str(result.at[idx, 'source_table']),
                            session_id=str(session_id),
                            mmu_id=str(result.at[idx, 'mmu_id'] or ''),
                            operator_name=str(result.at[idx, 'operator_name'] or ''),
                            timestamp=str(start),
                        )

                    end_ts = start + pd.Timedelta(minutes=capped) if pd.notna(start) else pd.NaT
                    result.at[idx, 'end_timestamp'] = end_ts
            else:
                next_idx = idxs[rank + 1]
                next_start = result.at[next_idx, 'start_timestamp']
                result.at[idx, 'end_timestamp'] = next_start

                if pd.notna(start) and pd.notna(next_start):
                    dur = (next_start - start).total_seconds() / 60

                    if dur < 0:
                        quality.add(
                            reason=f'Negative duration ({dur:.1f} min) — possible duplicate/out-of-order timestamp',
                            source_table=str(result.at[idx, 'source_table']),
                            session_id=str(session_id),
                            mmu_id=str(result.at[idx, 'mmu_id'] or ''),
                            timestamp=str(start),
                        )
                        result.at[idx, 'is_exception'] = True
                        existing = str(result.at[idx, 'exception_reason'] or '')
                        result.at[idx, 'exception_reason'] = '; '.join(
                            filter(None, [existing, f'Negative duration {dur:.1f} min'])
                        )
                        dur = 0.0

                    if dur > max_dur:
                        quality.add(
                            reason=f'Duration {dur:.0f} min exceeds threshold {max_dur} min',
                            source_table=str(result.at[idx, 'source_table']),
                            session_id=str(session_id),
                            mmu_id=str(result.at[idx, 'mmu_id'] or ''),
                            timestamp=str(start),
                        )
                        result.at[idx, 'is_exception'] = True
                        existing = str(result.at[idx, 'exception_reason'] or '')
                        result.at[idx, 'exception_reason'] = '; '.join(
                            filter(None, [existing, f'Duration {dur:.0f} min exceeds threshold'])
                        )

                    result.at[idx, 'duration_minutes'] = dur
                else:
                    result.at[idx, 'duration_minutes'] = None

    return result[TIMELINE_COLUMNS]
