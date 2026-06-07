"""
Precompute the amalgamated dashboard datasets and publish them to S3 as JSON,
so the data API can serve them fast (no heavy compute per request).

Reuses the EXACT proven amalgamation (src/aws_source.load_from_aws), so there is
no second implementation to drift. Run on a schedule (GitHub Action / cron /
scheduled Lambda). Writes:

    s3://<bucket>/dashboard/<window>/timeline.json
    s3://<bucket>/dashboard/<window>/prestart.json
    s3://<bucket>/dashboard/<window>/exceptions.json
    s3://<bucket>/dashboard/<window>/meta.json   ({generated_at, counts})

Env:
    DATA_BUCKET           target bucket (e.g. orica-kansanshi-jotform-prod-432046692351)
    SUBMISSIONS_TABLE     e.g. orica-kansanshi-jotform-submissions-prod
    AWS_REGION            us-east-1
    WINDOWS               optional CSV, default "7d,30d,90d,mtd"
    AWS credentials       standard chain (the precompute IAM user)

Usage:
    python scripts/precompute_to_s3.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.aws_source import load_from_aws  # noqa: E402

BUCKET = os.environ["DATA_BUCKET"]
REGION = os.environ.get("AWS_REGION", "us-east-1")
WINDOWS = [w.strip() for w in os.environ.get("WINDOWS", "7d,30d,90d,mtd").split(",") if w.strip()]

s3 = boto3.client("s3", region_name=REGION)


def window_days(window: str) -> int:
    w = window.lower()
    if w == "mtd":
        now = datetime.now(timezone.utc)
        return now.day  # days since the 1st (good enough for month-to-date)
    if w.endswith("d"):
        return int(w[:-1])
    if len(w) == 7 and w[4] == "-":   # explicit YYYY-MM → ~31 days back from now is wrong; skip
        return 31
    return 7


def put(window: str, name: str, body: str) -> None:
    s3.put_object(
        Bucket=BUCKET, Key=f"dashboard/{window}/{name}",
        Body=body.encode("utf-8"), ContentType="application/json",
    )


def main() -> None:
    for window in WINDOWS:
        days = window_days(window)
        print(f"[{window}] amalgamating last {days} days …")
        timeline, prestart, exceptions = load_from_aws(window_days=days)

        # to_json handles dates (ISO) and NaN (null) for us.
        put(window, "timeline.json", timeline.to_json(orient="records", date_format="iso"))
        put(window, "prestart.json", prestart.to_json(orient="records", date_format="iso"))
        put(window, "exceptions.json", exceptions.to_json(orient="records", date_format="iso"))
        put(window, "meta.json", json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window": window,
            "counts": {"timeline": len(timeline), "prestart": len(prestart), "exceptions": len(exceptions)},
        }))
        print(f"[{window}] published: timeline={len(timeline)} prestart={len(prestart)} exceptions={len(exceptions)}")

    print("Done.")


if __name__ == "__main__":
    main()
