#!/usr/bin/env python3
"""Diagnostic: dump the raw key/value pairs for Event Log records whose activity
matches a substring (default "breakdown"), so we can see the exact JotForm field
keys for breakdown category / type / additional info.

Run locally with prod AWS creds:
    AWS_PROFILE=imining-dev \
    DATA_BUCKET=orica-kansanshi-jotform-prod-432046692351 \
    SUBMISSIONS_TABLE=orica-kansanshi-jotform-submissions-prod \
    AWS_REGION=us-east-1 \
    python3 scripts/diag_event.py breakdown
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.aws_source import _norm, settings, FORM_TYPE_BY_ID  # noqa: E402

EVENT_FORMS = [fid for fid, t in FORM_TYPE_BY_ID.items() if t == "event_log"]


def scan(activity_sub: str, window_days: int, want: int):
    import boto3
    cfg = settings()
    ddb = boto3.client("dynamodb", region_name=cfg["region"])
    s3 = boto3.client("s3", region_name=cfg["region"])
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=window_days)
    found, scanned = [], 0
    for form_id in EVENT_FORMS:
        kwargs = {
            "TableName": cfg["submissions_table"], "IndexName": "form-received-index",
            "KeyConditionExpression": "form_id = :f AND received_at BETWEEN :s AND :e",
            "ScanIndexForward": False,
            "ExpressionAttributeValues": {":f": {"S": form_id},
                ":s": {"S": start.isoformat()}, ":e": {"S": end.isoformat()}},
        }
        while True:
            resp = ddb.query(**kwargs)
            for it in resp.get("Items", []):
                ck = it.get("clean_key", {}).get("S")
                if not ck:
                    continue
                scanned += 1
                if scanned % 25 == 0:
                    print(f"    ...scanned {scanned}, {len(found)} matched", flush=True)
                try:
                    rec = json.loads(s3.get_object(Bucket=cfg["bucket"], Key=ck)["Body"].read())
                except Exception:
                    continue
                if activity_sub in (_norm(rec).get("activity") or "").lower():
                    found.append(rec)
                    if len(found) >= want:
                        return found, scanned
            if "LastEvaluatedKey" in resp:
                kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            else:
                break
    return found, scanned


def main(activity_sub: str = "breakdown", window_days: int = 60, show: int = 5):
    import os
    print(f">>> diag_event starting (activity contains {activity_sub!r})", flush=True)
    print(f"    DATA_BUCKET={os.environ.get('DATA_BUCKET')!r} SUBMISSIONS_TABLE={os.environ.get('SUBMISSIONS_TABLE')!r}", flush=True)
    print(f"    scanning Event Log ({window_days}d, newest first)...", flush=True)
    recs, scanned = scan(activity_sub.lower(), window_days, show)
    print(f"\nscanned {scanned} event records; found {len(recs)} matching {activity_sub!r}\n", flush=True)
    if not recs:
        print("No matches — widen window or check the activity label spelling.", flush=True)
        return
    for i, r in enumerate(recs):
        raw = r.get("raw_submission") or r.get("data") or {}
        print(f"[{i+1}] submission_id={r.get('submission_id')}  activity={_norm(r).get('activity')!r}")
        print("  raw key -> value:")
        for k, v in raw.items():
            print(f"     {k!r}: {v!r}")
        print("-" * 70)


if __name__ == "__main__":
    sub = sys.argv[1] if len(sys.argv) > 1 else "breakdown"
    wd = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    try:
        main(activity_sub=sub, window_days=wd)
    except Exception:
        import traceback
        print("\n!!! diag_event failed:", flush=True)
        traceback.print_exc()
        sys.exit(1)
