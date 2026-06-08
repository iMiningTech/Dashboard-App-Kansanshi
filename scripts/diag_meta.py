#!/usr/bin/env python3
"""Diagnostic: show what the precompute last published to S3 for each window —
generated_at + row counts, and the actual length of timeline.json. Tells us
instantly whether the dashboard is empty because S3 has no data (precompute
problem) vs the front-end/API (S3 has data but the UI shows nothing).

    AWS_PROFILE=imining-dev \
    DATA_BUCKET=orica-kansanshi-jotform-prod-432046692351 \
    AWS_REGION=us-east-1 \
    python3 scripts/diag_meta.py
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.aws_source import settings  # noqa: E402

WINDOWS = ["7d", "30d", "90d", "mtd"]


def main():
    import boto3
    cfg = settings()
    s3 = boto3.client("s3", region_name=cfg["region"])
    bucket = cfg["bucket"]
    print(f"bucket={bucket!r}\n", flush=True)
    for w in WINDOWS:
        prefix = f"dashboard/{w}"
        line = f"[{w}] "
        try:
            meta = json.loads(s3.get_object(Bucket=bucket, Key=f"{prefix}/meta.json")["Body"].read())
            line += f"generated_at={meta.get('generated_at')}  counts={meta.get('counts')}"
        except Exception as e:
            line += f"meta.json MISSING/err: {e}"
        try:
            tl = json.loads(s3.get_object(Bucket=bucket, Key=f"{prefix}/timeline.json")["Body"].read())
            line += f"  | timeline.json rows={len(tl)}"
            if tl:
                dates = sorted({(r.get('reporting_date') or '')[:10] for r in tl if r.get('reporting_date')})
                line += f"  span={dates[0]}..{dates[-1]}" if dates else ""
        except Exception as e:
            line += f"  | timeline.json err: {e}"
        print(line, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("\n!!! diag_meta failed:", flush=True)
        traceback.print_exc()
        sys.exit(1)
