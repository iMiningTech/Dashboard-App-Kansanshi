"""
--inspect mode: scan input CSVs, print headers, and generate/update a starter mappings.yaml.
Auto-detection uses keyword heuristics to pre-fill likely column mappings.
"""
import glob
import logging
import os
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yaml

from src.utils import standardize_column_name

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristic keyword tables
# ---------------------------------------------------------------------------

# Keywords (in standardized column names) that suggest each canonical field,
# per source type.  Order matters — first match wins.
FIELD_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    'shift_log': {
        'operator_name':         ['operator', 'driver', 'employee', 'name', 'staff', 'person'],
        'mmu_id':                ['mmu', 'truck', 'vehicle', 'machine', 'unit', 'equip'],
        'shift_start_timestamp': ['start', 'begin', 'login', 'clock_in', 'commenc'],
        'shift_end_timestamp':   ['end', 'finish', 'logout', 'clock_out', 'complet'],
        'reporting_date':        ['date', 'shift_date', 'report'],
    },
    'event_log': {
        'operator_name':     ['operator', 'driver', 'employee', 'name', 'staff'],
        'mmu_id':            ['mmu', 'truck', 'vehicle', 'machine', 'unit', 'equip'],
        'timestamp':         ['submission', 'time', 'timestamp', 'logged', 'record', 'datetime'],
        'activity_type':     ['activity', 'type', 'action', 'event', 'task'],
        'activity_category': ['category', 'cat', 'group', 'class', 'section'],
        'activity_detail':   ['detail', 'description', 'note', 'specify', 'comment', 'remark'],
        'reporting_date':    ['date', 'report'],
    },
    'toolbox_talk': {
        'operator_name': ['operator', 'driver', 'employee', 'name', 'staff'],
        'mmu_id':        ['mmu', 'truck', 'vehicle', 'machine', 'unit', 'equip'],
        'timestamp':     ['submission', 'time', 'timestamp', 'logged', 'record', 'datetime'],
        'reporting_date':['date', 'report'],
    },
    'prestart_checklist': {
        'mmu_id':                ['mmu', 'truck', 'vehicle', 'machine', 'unit', 'equip'],
        'operator_name':         ['operator', 'driver', 'employee', 'name', 'staff'],
        'inspection_timestamp':  ['submission', 'time', 'timestamp', 'inspect', 'logged', 'record'],
        'reporting_date':        ['date', 'report'],
        'comments':              ['comment', 'note', 'remark', 'defect', 'fault', 'issue'],
    },
}

# Keywords in filenames that suggest a source type
FILENAME_KEYWORDS: Dict[str, List[str]] = {
    'shift_log':          ['shift', 'login', 'session', 'logon', 'shiftstart', 'startshift'],
    'event_log':          ['event', 'activity', 'operation', 'actlog'],
    'toolbox_talk':       ['toolbox', 'tbt', 'safety_talk', 'talk'],
    'prestart_checklist': ['prestart', 'pre_start', 'pre-start', 'checklist', 'inspection'],
}

# System / metadata columns that are unlikely to be checklist items
_METADATA_KEYWORDS = {
    'submission', 'ip', 'id', 'form', 'index', 'operator', 'mmu',
    'truck', 'vehicle', 'machine', 'unit', 'equip', 'date', 'time',
    'name', 'driver', 'employee', 'comment', 'note', 'remark',
}


# ---------------------------------------------------------------------------
# Core inspect logic
# ---------------------------------------------------------------------------

def detect_source_type(filename: str) -> Optional[str]:
    fname = os.path.splitext(os.path.basename(filename))[0].lower()
    fname = fname.replace(' ', '_').replace('-', '_')
    for source, keywords in FILENAME_KEYWORDS.items():
        for kw in keywords:
            if kw in fname:
                return source
    return None


def auto_detect_mapping(columns: List[str], field_hints: Dict[str, List[str]]) -> Dict[str, Optional[str]]:
    """
    Return {canonical: original_column} using keyword heuristics.
    Each canonical field gets the first column whose standardized name contains a hint keyword.
    """
    mapping: Dict[str, Optional[str]] = {canonical: None for canonical in field_hints}
    std_to_original = {standardize_column_name(c): c for c in columns}

    for canonical, keywords in field_hints.items():
        for std_col, orig_col in std_to_original.items():
            for kw in keywords:
                if kw in std_col and mapping[canonical] is None:
                    mapping[canonical] = orig_col
                    break
    return mapping


def _guess_checklist_columns(columns: List[str]) -> List[str]:
    """Identify columns that look like checklist items rather than metadata."""
    result = []
    for col in columns:
        std = standardize_column_name(col)
        is_meta = any(kw in std for kw in _METADATA_KEYWORDS)
        if not is_meta:
            result.append(col)
    return result


def _load_existing_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        return {}
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _read_headers(filepath: str) -> Tuple[List[str], Optional[str]]:
    """Return (column_list, error_message_or_None)."""
    try:
        df = pd.read_csv(filepath, nrows=0, dtype=str, encoding='utf-8-sig')
        return list(df.columns), None
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(filepath, nrows=0, dtype=str, encoding='latin-1')
            return list(df.columns), None
        except Exception as e:
            return [], str(e)
    except Exception as e:
        return [], str(e)


def inspect_inputs(input_dir: str, config_path: str) -> None:
    """
    Main --inspect entry point.
    Prints a structured header report and writes/updates mappings.yaml.
    """
    csv_files = sorted(glob.glob(os.path.join(input_dir, '*.csv')))

    if not csv_files:
        print(f"\nNo CSV files found in: {input_dir}")
        print("Place your Jotform CSV exports in the /input folder and re-run --inspect.")
        return

    print(f"\n{'='*65}")
    print(f"  INSPECTION - {len(csv_files)} CSV file(s) found in /input")
    print(f"{'='*65}\n")

    detected: Dict[str, dict] = {}

    for filepath in csv_files:
        filename = os.path.basename(filepath)
        columns, err = _read_headers(filepath)

        source_type = detect_source_type(filename)
        label = source_type or '(unknown — assign in config)'

        print(f"  File : {filename}")
        print(f"  Type : {label}")

        if err:
            print(f"  ERROR: {err}\n")
            continue

        print(f"  Cols : {len(columns)}")
        for col in columns:
            std = standardize_column_name(col)
            suffix = f"  (std: '{std}')" if std != col.strip().lower().replace(' ', '_') else ''
            print(f"         - {col!r}{suffix}")
        print()

        if source_type and source_type not in detected:
            detected[source_type] = {'filename': filename, 'columns': columns}
        elif not source_type:
            detected[f'unknown_{filename}'] = {'filename': filename, 'columns': columns}

    _generate_config(config_path, detected)
    print(f"  Config written : {config_path}")
    print()
    print("  Next steps:")
    print("  1. Open config/mappings.yaml")
    print("  2. For each source, confirm or correct the column mappings")
    print("  3. Add mmu_aliases / operator_aliases if needed")
    print("  4. Run:  python src/normalize.py --run\n")


def _generate_config(config_path: str, detected: Dict[str, dict]) -> None:
    existing = _load_existing_config(config_path)

    config = {
        'settings': {
            **{
                'timezone': None,
                'max_activity_duration_minutes': 240,
                'default_shift_end_if_missing': None,
            },
            **(existing.get('settings') or {}),
        },
        'sources': {},
        'mmu_aliases': existing.get('mmu_aliases') or {},
        'operator_aliases': existing.get('operator_aliases') or {},
        'fault_keywords': existing.get('fault_keywords') or [
            'fail', 'no', 'defect', 'fault', 'broken', 'damaged', 'missing',
        ],
    }

    # Build source blocks — known sources first in a logical order
    all_source_names = ['shift_log', 'event_log', 'toolbox_talk', 'prestart_checklist']
    # Then any unknowns
    all_source_names += [k for k in detected if k not in all_source_names]

    for source_name in all_source_names:
        existing_src = (existing.get('sources') or {}).get(source_name) or {}

        # A source is "already configured" if it has a real (non-placeholder) filename.
        # In that case we protect the existing mappings and only fill in null entries.
        is_configured = (
            existing_src.get('filename')
            and not str(existing_src.get('filename', '')).startswith('FILL_IN_')
        )

        if source_name in detected:
            info = detected[source_name]
            hints = FIELD_KEYWORDS.get(source_name, {})

            if is_configured:
                # --- Protect existing config ---
                # Start from existing columns dict exactly; only fill null entries
                # with auto-detect. Do NOT add new canonical fields not already present.
                existing_cols = dict(existing_src.get('columns') or {})
                auto_map = auto_detect_mapping(info['columns'], hints)
                merged_map = {}
                for canonical, existing_val in existing_cols.items():
                    if existing_val is None and canonical in auto_map:
                        merged_map[canonical] = auto_map[canonical]  # fill blank
                    else:
                        merged_map[canonical] = existing_val          # keep as-is
            else:
                # --- Fresh auto-detect ---
                auto_map = auto_detect_mapping(info['columns'], hints)
                merged_map = {**{k: None for k in hints.keys()}, **auto_map}

            src_block: dict = {
                'filename': existing_src.get('filename') or info['filename'],
                'columns': merged_map,
            }

            # Preserve any extra source-level keys (start_values, end_values, etc.)
            for k, v in existing_src.items():
                if k not in ('filename', 'columns', 'checklist_item_columns'):
                    src_block[k] = v

            if source_name == 'prestart_checklist':
                # Always keep empty list — prestart.py auto-detects >> STATUS pattern
                existing_cl = existing_src.get('checklist_item_columns')
                src_block['checklist_item_columns'] = existing_cl if existing_cl is not None else []

        else:
            # File not detected in /input — emit placeholder
            hints = FIELD_KEYWORDS.get(source_name, {})
            src_block = {
                'filename': existing_src.get('filename') or f'FILL_IN_{source_name}.csv',
                'columns': existing_src.get('columns') or {k: None for k in hints},
            }
            for k, v in existing_src.items():
                if k not in ('filename', 'columns', 'checklist_item_columns'):
                    src_block[k] = v
            if source_name == 'prestart_checklist':
                src_block['checklist_item_columns'] = existing_src.get('checklist_item_columns') or []

        config['sources'][source_name] = src_block

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
