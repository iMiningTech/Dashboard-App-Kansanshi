#!/usr/bin/env python3
"""
MMU Operations CSV Normalizer — Orica / Kansanshi

Processes Jotform CSV exports and produces clean, dashboard-ready outputs.

Usage:
    python src/normalize.py --inspect    Scan CSVs and generate starter config
    python src/normalize.py --run        Run normalization using configured mappings
    python src/normalize.py --run -v     Verbose / debug logging
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path so "from src.xxx import" works when called as
# "python src/normalize.py" from the project directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config
from src.inspector import inspect_inputs
from src.loader import load_source
from src.sessions import build_sessions
from src.timeline import build_timeline, calculate_durations
from src.prestart import normalize_prestart
from src.quality import QualityCollector

INPUT_DIR = PROJECT_ROOT / 'input'
OUTPUT_DIR = PROJECT_ROOT / 'output'
CONFIG_PATH = PROJECT_ROOT / 'config' / 'mappings.yaml'


def setup_logging(verbose: bool = False) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_file = OUTPUT_DIR / 'normalize.log'
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)-7s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
        ],
    )
    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def cmd_inspect(_args) -> None:
    inspect_inputs(str(INPUT_DIR), str(CONFIG_PATH))


def cmd_run(args) -> None:
    logger = logging.getLogger(__name__)

    if not CONFIG_PATH.exists():
        logger.error(
            "Config not found: %s\n"
            "Run --inspect first to generate a starter config, then edit the mappings.",
            CONFIG_PATH,
        )
        sys.exit(1)

    config = load_config(str(CONFIG_PATH))
    quality = QualityCollector()

    # ── Load ──────────────────────────────────────────────────────────────────
    logger.info("Loading sources from %s …", INPUT_DIR)
    shift_df   = load_source('shift_log',          config, str(INPUT_DIR), quality)
    event_df   = load_source('event_log',           config, str(INPUT_DIR), quality)
    toolbox_df = load_source('toolbox_talk',        config, str(INPUT_DIR), quality)
    prestart_df = load_source('prestart_checklist', config, str(INPUT_DIR), quality)

    # ── Sessions ──────────────────────────────────────────────────────────────
    logger.info("Building shift sessions …")
    sessions = build_sessions(shift_df, config, quality)
    logger.info("  → %d sessions", len(sessions))

    # ── Timeline ──────────────────────────────────────────────────────────────
    logger.info("Building activity timeline …")
    timeline = build_timeline(sessions, event_df, toolbox_df, config, quality)

    logger.info("Calculating durations …")
    timeline = calculate_durations(timeline, config, quality)
    logger.info("  → %d timeline rows", len(timeline))

    # ── Pre-start ─────────────────────────────────────────────────────────────
    logger.info("Normalizing pre-start checklist …")
    prestart_report = normalize_prestart(prestart_df, config, quality)
    logger.info("  → %d pre-start rows", len(prestart_report))

    # ── Write outputs ─────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timeline_path  = OUTPUT_DIR / 'normalized_activity_timeline.csv'
    prestart_path  = OUTPUT_DIR / 'normalized_prestart_report.csv'
    exceptions_path = OUTPUT_DIR / 'data_quality_exceptions.csv'

    timeline.to_csv(timeline_path, index=False, encoding='utf-8')
    prestart_report.to_csv(prestart_path, index=False, encoding='utf-8')
    exceptions_df = quality.get_df()
    exceptions_df.to_csv(exceptions_path, index=False, encoding='utf-8')

    logger.info("")
    logger.info("Output files written to %s:", OUTPUT_DIR)
    logger.info("  %-40s  %d rows", 'normalized_activity_timeline.csv', len(timeline))
    logger.info("  %-40s  %d rows", 'normalized_prestart_report.csv',   len(prestart_report))
    logger.info("  %-40s  %d rows", 'data_quality_exceptions.csv',       len(exceptions_df))
    if quality.count():
        logger.warning("%d data quality exceptions — review data_quality_exceptions.csv", quality.count())


# ── Entry point ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='normalize.py',
        description='MMU Operations CSV Normalizer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  python src/normalize.py --inspect\n'
            '  python src/normalize.py --run\n'
            '  python src/normalize.py --run --verbose\n'
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect', action='store_true',
                      help='Scan /input CSVs and generate/update config/mappings.yaml')
    mode.add_argument('--run', action='store_true',
                      help='Run full normalization and write output CSVs')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable debug-level logging')
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.inspect:
        cmd_inspect(args)
    elif args.run:
        cmd_run(args)


if __name__ == '__main__':
    main()
