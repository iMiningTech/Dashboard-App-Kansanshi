"""
Data quality exception collector.
Accumulates problematic rows throughout processing and exports to CSV.
"""
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

EXCEPTION_COLUMNS = [
    'source_table',
    'source_file',
    'source_row_index',
    'exception_reason',
    'field',
    'raw_value',
    'session_id',
    'mmu_id',
    'operator_name',
    'timestamp',
]


class QualityCollector:
    """Accumulates data quality exceptions without stopping the pipeline."""

    def __init__(self):
        self._records = []

    def add(
        self,
        reason: str,
        source_table: str = '',
        source_file: str = '',
        source_row_index=None,
        field: str = '',
        raw_value=None,
        session_id: str = '',
        mmu_id: str = '',
        operator_name: str = '',
        timestamp=None,
        **extra,
    ) -> None:
        record = {
            'source_table': source_table,
            'source_file': source_file,
            'source_row_index': source_row_index,
            'exception_reason': reason,
            'field': field,
            'raw_value': raw_value,
            'session_id': session_id,
            'mmu_id': mmu_id,
            'operator_name': operator_name,
            'timestamp': timestamp,
        }
        record.update(extra)
        self._records.append(record)
        logger.debug("Exception [%s|row %s]: %s", source_table, source_row_index, reason)

    def add_from_row(self, row: pd.Series, reason: str, source_table: str, field: str = '') -> None:
        """Add an exception from a DataFrame row, extracting common fields automatically."""
        self.add(
            reason=reason,
            source_table=source_table,
            source_file=str(row.get('_source_file', '')),
            source_row_index=row.get('_source_row_index'),
            field=field,
            mmu_id=str(row.get('mmu_id', '')),
            operator_name=str(row.get('operator_name', '')),
            timestamp=str(row.get('timestamp', row.get('shift_start_timestamp', ''))),
        )

    def get_df(self) -> pd.DataFrame:
        if not self._records:
            return pd.DataFrame(columns=EXCEPTION_COLUMNS)
        df = pd.DataFrame(self._records)
        # Ensure standard columns exist
        for col in EXCEPTION_COLUMNS:
            if col not in df.columns:
                df[col] = ''
        return df[EXCEPTION_COLUMNS + [c for c in df.columns if c not in EXCEPTION_COLUMNS]]

    def count(self) -> int:
        return len(self._records)
