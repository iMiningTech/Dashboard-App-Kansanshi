"""Precompute Lambda — runs the EXISTING amalgamation (src.aws_source.load_from_aws)
and publishes the dashboard JSON to S3. Same single implementation as the CLI
script; this just wraps it for event-driven execution.

Triggers:
  • SQS  (webhook nudge on each submission)  → ROUTINE_WINDOWS (7d/30d/mtd — fast)
  • EventBridge schedule (backstop)           → ALL_WINDOWS  (incl. heavy 90d)
  • Manual invoke {"windows": [...], "force": true}

Debounce/efficiency: reserved concurrency 1 + SQS batch window coalesce bursts,
and a freshness guard skips a run when no submission is newer than the last
published meta.generated_at.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

# src/ and config/ are copied alongside this file by the Makefile build.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.aws_source import load_from_aws  # noqa: E402

BUCKET = os.environ["DATA_BUCKET"]
REGION = os.environ.get("AWS_REGION", "us-east-1")
SUB = os.environ.get("SUBMISSIONS_TABLE", "")
ROUTINE = [w.strip() for w in os.environ.get("ROUTINE_WINDOWS", "7d,30d,mtd").split(",") if w.strip()]
ALLW = [w.strip() for w in os.environ.get("ALL_WINDOWS", "7d,30d,90d,mtd").split(",") if w.strip()]
# The 4 form IDs (for the freshness check across all streams).
FORM_IDS = [w.strip() for w in os.environ.get(
    "FORM_IDS", "260905029221954,260804815809967,260804512261953,261247755437969"
).split(",") if w.strip()]

s3 = boto3.client("s3", region_name=REGION)
ddb = boto3.client("dynamodb", region_name=REGION)


def window_days(window: str) -> int:
    w = window.lower()
    if w == "mtd":
        return datetime.now(timezone.utc).day
    if w.endswith("d"):
        return int(w[:-1])
    return 7


def _put(window: str, name: str, body: str) -> None:
    s3.put_object(Bucket=BUCKET, Key=f"dashboard/{window}/{name}",
                  Body=body.encode("utf-8"), ContentType="application/json")


def newest_received() -> str:
    """Most recent received_at across all four submission streams (19-char)."""
    newest = ""
    for fid in FORM_IDS:
        try:
            r = ddb.query(TableName=SUB, IndexName="form-received-index",
                          KeyConditionExpression="form_id = :f",
                          ExpressionAttributeValues={":f": {"S": fid}},
                          ScanIndexForward=False, Limit=1)
            items = r.get("Items", [])
            if items:
                ra = (items[0].get("received_at", {}).get("S") or "")[:19]
                if ra > newest:
                    newest = ra
        except Exception as e:  # never let the guard block a run
            print("freshness query failed for", fid, e)
    return newest


def last_generated(window: str) -> str:
    try:
        o = s3.get_object(Bucket=BUCKET, Key=f"dashboard/{window}/meta.json")
        return (json.loads(o["Body"].read()).get("generated_at") or "")[:19]
    except Exception:
        return ""


def run(windows) -> None:
    for window in windows:
        days = window_days(window)
        print(f"[{window}] amalgamating last {days} days …", flush=True)
        timeline, prestart, exceptions = load_from_aws(window_days=days)
        _put(window, "timeline.json", timeline.to_json(orient="records", date_format="iso"))
        _put(window, "prestart.json", prestart.to_json(orient="records", date_format="iso"))
        _put(window, "exceptions.json", exceptions.to_json(orient="records", date_format="iso"))
        _put(window, "meta.json", json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window": window,
            "counts": {"timeline": len(timeline), "prestart": len(prestart), "exceptions": len(exceptions)},
        }))
        print(f"[{window}] published t={len(timeline)} p={len(prestart)} e={len(exceptions)}", flush=True)


def lambda_handler(event, context):
    event = event or {}
    source = event.get("source")
    explicit = event.get("windows")
    force = bool(event.get("force")) or bool(explicit)

    if source == "aws.events":
        windows = ALLW           # backstop → full refresh incl. heavy 90d
    elif "Records" in event:
        windows = ROUTINE        # SQS nudge → fast windows only
    else:
        windows = explicit or ROUTINE

    if not force:
        # Guard against the STALEST window we're about to generate — not windows[0].
        # windows[0] is "7d", which the SQS nudge keeps perpetually fresh, so guarding
        # on it made the backstop skip forever and the heavy 90d window never refreshed.
        newest = newest_received()
        gens = [g for g in (last_generated(w) for w in (windows or ["30d"])) if g]
        gen = min(gens) if gens else ""
        if newest and gen and newest <= gen:
            print(f"all target windows fresh as of {gen} — skipping", flush=True)
            return {"skipped": True, "since": gen}

    run(windows)
    return {"ran": windows}
