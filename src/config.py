"""
Config loader — reads mappings.yaml and provides typed access.
"""
import logging
import os
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Default settings applied when not present in config
SETTING_DEFAULTS = {
    'timezone': None,
    'max_activity_duration_minutes': 240,
    'default_shift_end_if_missing': None,
}


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load and validate mappings.yaml.
    Returns a dict with keys: settings, sources, mmu_aliases, operator_aliases, fault_keywords.
    """
    if not os.path.exists(config_path):
        logger.warning("Config not found at %s. Run --inspect first to generate it.", config_path)
        return _empty_config()

    with open(config_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}

    config = {
        'settings': {**SETTING_DEFAULTS, **(raw.get('settings') or {})},
        'sources': raw.get('sources') or {},
        'mmu_aliases': raw.get('mmu_aliases') or {},
        'operator_aliases': raw.get('operator_aliases') or {},
        'fault_keywords': raw.get('fault_keywords') or [
            'fail', 'no', 'defect', 'fault', 'broken', 'damaged', 'missing'
        ],
    }

    logger.info("Config loaded from %s", config_path)
    return config


def get_source_config(config: Dict[str, Any], source_name: str) -> Dict[str, Any]:
    """Return the config block for a named source, with safe defaults."""
    return config.get('sources', {}).get(source_name) or {}


def get_column_map(config: Dict[str, Any], source_name: str) -> Dict[str, Optional[str]]:
    """
    Return {canonical_field: original_header_string} for a source.
    Values of None mean 'not configured yet'.
    """
    src = get_source_config(config, source_name)
    return src.get('columns') or {}


def _empty_config() -> Dict[str, Any]:
    return {
        'settings': dict(SETTING_DEFAULTS),
        'sources': {},
        'mmu_aliases': {},
        'operator_aliases': {},
        'fault_keywords': ['fail', 'no', 'defect', 'fault', 'broken', 'damaged', 'missing'],
    }
