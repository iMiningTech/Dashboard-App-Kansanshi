"""
AWS data source for the dashboard.

Replaces the CSV loader: fetches JotForm submissions from the AWS pipeline
(DynamoDB submissions index + S3 clean/ JSON), reshapes them into the SAME
per-form canonical frames that src/loader.load_source produced, then reuses the
existing amalgamation (build_sessions / build_timeline / calculate_durations +
QualityCollector) plus a schema-driven Pre-Start matrix exploder to emit the
three dashboard datasets:

    timeline (normalized_activity_timeline)
    prestart (normalized_prestart_report)
    exceptions (data_quality_exceptions)

Design: compute-on-read over a bounded window (default last 7 days), cached by
the dashboard. The same build_outputs() can later be lifted into a scheduled
Lambda for monthly precomputed summaries — no widget changes.

Credentials/config come from env or Streamlit secrets (see settings()).
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from src.config import load_config
from src.sessions import build_sessions
from src.timeline import build_timeline, calculate_durations
from src.quality import QualityCollector
from src.utils import normalize_text

logger = logging.getLogger(__name__)

# Form IDs -> the canonical source names the pipeline uses.
FORM_TYPE_BY_ID = {
    "260905029221954": "shift_log",
    "260804815809967": "event_log",
    "261247755437969": "toolbox_talk",
    "260804512261953": "prestart_checklist",
}

# Question TEXT (from JotForm schema) for the extra event/toolbox fields not in
# the slim normalized record. These match the CSV headers in config/mappings.yaml.
TEXT_BREAKDOWN_CATEGORY = "Breakdown Category:"
TEXT_ADDITIONAL_INFO = "Additional Information (Optional):"
TEXT_TOOLBOX_DETAIL = "Questions Or Concerns (Optional):"

_QID_RE = re.compile(r"^q(\d+)_")


# ──────────────────────────────────────────────────────────────────────────────
# Config / credentials
# ──────────────────────────────────────────────────────────────────────────────

def settings() -> Dict[str, str]:
    """
    Resolve AWS + table/bucket settings from env vars, falling back to Streamlit
    secrets if available. Keeps secrets out of code.
    """
    cfg = {
        "region": os.environ.get("AWS_REGION", "us-east-1"),
        "submissions_table": os.environ.get("SUBMISSIONS_TABLE", "orica-kansanshi-jotform-submissions-prod"),
        "bucket": os.environ.get("DATA_BUCKET", ""),
    }
    try:
        import streamlit as st  # type: ignore
        if hasattr(st, "secrets") and "aws" in st.secrets:
            s = st.secrets["aws"]
            cfg["region"] = s.get("region", cfg["region"])
            cfg["submissions_table"] = s.get("submissions_table", cfg["submissions_table"])
            cfg["bucket"] = s.get("bucket", cfg["bucket"])
            # boto3 picks these up from the environment
            if s.get("access_key_id"):
                os.environ.setdefault("AWS_ACCESS_KEY_ID", s["access_key_id"])
                os.environ.setdefault("AWS_SECRET_ACCESS_KEY", s["secret_access_key"])
                os.environ.setdefault("AWS_DEFAULT_REGION", cfg["region"])
    except Exception:  # streamlit not present (e.g. local/CLI) — env vars only
        pass
    return cfg


# ──────────────────────────────────────────────────────────────────────────────
# Fetch
# ──────────────────────────────────────────────────────────────────────────────

def fetch_clean_records(
    window_days: int = 7,
    *,
    end: Optional[datetime] = None,
    cfg: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Pull full clean records for all four forms within [end-window, end].

    Uses the submissions table GSI (form-received-index: form_id + received_at)
    to find the submissions in range, then reads each clean/ object from S3.
    """
    import boto3  # imported lazily so unit tests of the pure logic need no AWS

    cfg = cfg or settings()
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(days=window_days)
    start_iso, end_iso = start.isoformat(), end.isoformat()

    ddb = boto3.client("dynamodb", region_name=cfg["region"])
    s3 = boto3.client("s3", region_name=cfg["region"])
    bucket = cfg["bucket"]
    table = cfg["submissions_table"]

    records: List[Dict[str, Any]] = []
    for form_id in FORM_TYPE_BY_ID:
        keys: List[str] = []
        kwargs = {
            "TableName": table,
            "IndexName": "form-received-index",
            "KeyConditionExpression": "form_id = :f AND received_at BETWEEN :s AND :e",
            "ExpressionAttributeValues": {
                ":f": {"S": form_id}, ":s": {"S": start_iso}, ":e": {"S": end_iso},
            },
        }
        while True:
            resp = ddb.query(**kwargs)
            for it in resp.get("Items", []):
                ck = it.get("clean_key", {}).get("S")
                if ck:
                    keys.append(ck)
            if "LastEvaluatedKey" in resp:
                kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            else:
                break

        for key in keys:
            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                records.append(json.loads(obj["Body"].read()))
            except Exception as e:  # one bad object shouldn't sink the load
                logger.warning("failed to read %s: %s", key, e)

    logger.info("fetched %d clean records (%s .. %s)", len(records), start_iso, end_iso)
    return records


# ──────────────────────────────────────────────────────────────────────────────
# Reshape clean records -> per-form canonical frames
# ──────────────────────────────────────────────────────────────────────────────

def _index_raw_by_qid(raw: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in (raw or {}).items():
        m = _QID_RE.match(k)
        if m:
            out[m.group(1)] = v
    return out

def _text_value_map(rec: Dict[str, Any]) -> Dict[str, Any]:
    """{question_text: scalar value} — for event/toolbox extra fields."""
    schema = rec.get("schema") or {}
    by_qid = _index_raw_by_qid(rec.get("raw_submission") or rec.get("data") or {})
    out: Dict[str, Any] = {}
    for qid, q in schema.items():
        if not isinstance(q, dict):
            continue
        text = (q.get("text") or "").strip()
        if not text:
            continue
        val = by_qid.get(str(q.get("qid", qid)))
        if isinstance(val, (list, dict)):
            continue  # matrices/composites handled elsewhere
        out[text] = val
    return out

def _norm(rec: Dict[str, Any]) -> Dict[str, Any]:
    return rec.get("normalized_submission") or {}

def _timestamp(rec: Dict[str, Any]) -> str:
    n = _norm(rec)
    return n.get("submitted_at") or rec.get("received_at") or ""

def build_frames(records: List[Dict[str, Any]], config: dict):
    """Return (shift_df, event_df, toolbox_df) as the loader would have."""
    mmu_aliases = config.get("mmu_aliases") or {}
    op_aliases = config.get("operator_aliases") or {}

    shift_rows, event_rows, toolbox_rows = [], [], []

    for i, rec in enumerate(records):
        form_id = rec.get("form_id") or (_norm(rec).get("form_id"))
        stype = FORM_TYPE_BY_ID.get(str(form_id))
        if not stype or stype == "prestart_checklist":
            continue
        n = _norm(rec)
        sid = rec.get("submission_id") or f"row{i}"
        operator = normalize_text(n.get("operator") or "", op_aliases)
        mmu = normalize_text(n.get("fleet_no") or "", mmu_aliases)
        ts = _timestamp(rec)
        base = {
            "operator_name": operator, "mmu_id": mmu, "timestamp": ts,
            "_source_file": sid, "_source_row_index": 0, "_source_name": stype,
        }
        if stype == "shift_log":
            base["shift_event_type"] = n.get("shift_event") or ""
            shift_rows.append(base)
        elif stype == "event_log":
            tmap = _text_value_map(rec)
            base["activity_type"] = n.get("activity") or ""
            base["activity_category"] = tmap.get(TEXT_BREAKDOWN_CATEGORY) or ""
            base["activity_detail"] = tmap.get(TEXT_ADDITIONAL_INFO) or ""
            event_rows.append(base)
        elif stype == "toolbox_talk":
            tmap = _text_value_map(rec)
            base["activity_detail"] = tmap.get(TEXT_TOOLBOX_DETAIL) or ""
            toolbox_rows.append(base)

    cols = ["_source_file", "_source_row_index"]
    shift_df = pd.DataFrame(shift_rows) if shift_rows else pd.DataFrame(columns=cols)
    event_df = pd.DataFrame(event_rows) if event_rows else pd.DataFrame(columns=cols)
    toolbox_df = pd.DataFrame(toolbox_rows) if toolbox_rows else pd.DataFrame(columns=cols)
    return shift_df, event_df, toolbox_df


# ──────────────────────────────────────────────────────────────────────────────
# Pre-Start exploder (schema-driven: control_matrix mrows/answers)
# ──────────────────────────────────────────────────────────────────────────────

PRESTART_COLUMNS = [
    "mmu_id", "operator_name", "inspection_timestamp", "reporting_date",
    "checklist_category", "checklist_item", "status", "fault_number",
    "comment", "fault_flag", "source_row_index", "source_file",
]

def _clean_label(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("\t", " ")).strip()

def _parse_maybe(v):
    """JSON-decode a string that looks like an object/array; else return as-is."""
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in ("[", "{"):
            try:
                return json.loads(s)
            except Exception:
                return v
    return v

# Friendly category when there's no schema text (backfilled records have none).
_NAME_CATEGORY = {
    "incab": "IN CAB CHECKS", "external": "EXTERNAL CHECKS",
    "quality": "QUALITY", "before": "BEFORE DRIVING OFF",
}

def _matrix_rows(value):
    """
    Return [(item_label_or_None, [status, fault_no, comment]), ...] if `value` is
    a checklist matrix, else None. Handles BOTH shapes:
      • live webhook:  [["FAULT","",""], ["OK","",""], ...]            (list of rows)
      • backfill API:  {"<item label>": "[\"FAULT\",\"\",\"\"]", ...}  (dict)
    """
    value = _parse_maybe(value)
    out = []
    if isinstance(value, list):
        for cell in value:
            cell = _parse_maybe(cell)
            if isinstance(cell, list):
                out.append((None, cell))
        return out or None
    if isinstance(value, dict):
        for label, cell in value.items():
            cell = _parse_maybe(cell)
            if isinstance(cell, list):
                out.append((label, cell))
        return out or None
    return None

def _category_for(name: str, schema: dict, qid: str) -> str:
    q = (schema or {}).get(qid)
    if isinstance(q, dict) and q.get("text"):
        return _clean_label(q["text"])
    nl = (name or "").lower()
    for frag, cat in _NAME_CATEGORY.items():
        if frag in nl:
            return cat
    return _clean_label(name)

def explode_prestart(records: List[Dict[str, Any]], config: dict) -> pd.DataFrame:
    """
    One row per (inspection, checklist item). Detects checklist matrices straight
    from the submission DATA (schema-independent), so it works for both live
    submissions (list-of-rows answers, with schema mrows for labels) and
    backfilled records (dict answers keyed by item label, no schema).
    """
    mmu_aliases = config.get("mmu_aliases") or {}
    op_aliases = config.get("operator_aliases") or {}
    fault_kw = [k.lower() for k in (config.get("fault_keywords") or [])]

    rows = []
    for rec in records:
        if FORM_TYPE_BY_ID.get(str(rec.get("form_id"))) != "prestart_checklist":
            continue
        n = _norm(rec)
        schema = rec.get("schema") or {}
        data = rec.get("raw_submission") or rec.get("data") or {}
        mmu = normalize_text(n.get("fleet_no") or "", mmu_aliases)
        operator = normalize_text(n.get("operator") or "", op_aliases)
        ts = _timestamp(rec)
        reporting_date = ts[:10] if ts else None
        sid = rec.get("submission_id") or ""

        for key, raw_val in data.items():
            m = re.match(r"^q(\d+)_(.*)$", key)
            if not m:
                continue
            qid, name = m.group(1), m.group(2)
            matrix = _matrix_rows(raw_val)
            if not matrix:
                continue
            category = _category_for(name, schema, qid)
            mrows = [x for x in (_clean_label(y) for y in str((schema.get(qid) or {}).get("mrows") or "").split("|")) if x]
            for idx, (label, cell) in enumerate(matrix):
                status = str(cell[0]).strip() if len(cell) > 0 and cell[0] is not None else ""
                fault_number = str(cell[1]).strip() if len(cell) > 1 and cell[1] is not None else ""
                comment = str(cell[2]).strip() if len(cell) > 2 and cell[2] is not None else ""
                item = _clean_label(label) if label else (mrows[idx] if idx < len(mrows) else f"item_{idx + 1}")
                fault_flag = any(k in status.lower() for k in fault_kw)
                rows.append({
                    "mmu_id": mmu or None,
                    "operator_name": operator or None,
                    "inspection_timestamp": ts or None,
                    "reporting_date": reporting_date,
                    "checklist_category": category,
                    "checklist_item": item,
                    "status": status,
                    "fault_number": fault_number,
                    "comment": comment,
                    "fault_flag": fault_flag,
                    "source_row_index": idx,
                    "source_file": sid,
                })
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=PRESTART_COLUMNS)


# ──────────────────────────────────────────────────────────────────────────────
# Top-level: records -> the 3 dashboard datasets
# ──────────────────────────────────────────────────────────────────────────────

def build_outputs(records: List[Dict[str, Any]], config: dict):
    """records -> (timeline_df, prestart_df, exceptions_df). Reuses the existing
    amalgamation verbatim; only the data source changed."""
    quality = QualityCollector()
    shift_df, event_df, toolbox_df = build_frames(records, config)

    sessions = build_sessions(shift_df, config, quality)
    timeline = build_timeline(sessions, event_df, toolbox_df, config, quality)
    timeline = calculate_durations(timeline, config, quality)

    prestart = explode_prestart(records, config)
    exceptions = quality.get_df()

    # Drop junk rows with no MMU assigned — they're not trustworthy analytics
    # (operator didn't fill the app properly). They remain captured in the
    # exceptions table for data-quality follow-up.
    def _has_mmu(df):
        if df.empty or "mmu_id" not in df.columns:
            return df
        return df[df["mmu_id"].notna() & (df["mmu_id"].astype(str).str.strip() != "")].reset_index(drop=True)
    timeline = _has_mmu(timeline)
    prestart = _has_mmu(prestart)

    return timeline, prestart, exceptions


def load_from_aws(window_days: int = 7, config_path: Optional[str] = None):
    """Fetch + amalgamate. This is the single function a scheduled monthly job
    would also call (with a month-long window)."""
    from pathlib import Path
    cp = config_path or str(Path(__file__).resolve().parent.parent / "config" / "mappings.yaml")
    config = load_config(cp)
    records = fetch_clean_records(window_days=window_days)
    return build_outputs(records, config)
