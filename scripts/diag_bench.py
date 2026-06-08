#!/usr/bin/env python3
"""Diagnostic: inspect real "Loading Explosives" Event Log records to see the
exact JotForm field label + value for the bench-location / specify fields.

Run locally with prod AWS creds, e.g.:
    AWS_PROFILE=imining-dev \
    DATA_BUCKET=orica-kansanshi-jotform-prod-432046692351 \
    SUBMISSIONS_TABLE=orica-kansanshi-jotform-submissions-prod \
    AWS_REGION=us-east-1 \
    python scripts/diag_bench.py

It prints, for the first few loading events: every schema text label, what the
text-value map (_text_value_map) returns for each, the raw_submission keys, and
flags anything mentioning bench/specify/location — so we can confirm the exact
label string the pipeline must match.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.aws_source import (  # noqa: E402
    fetch_clean_records, _norm, _text_value_map, _index_raw_by_qid,
    FORM_TYPE_BY_ID, TEXT_BENCH_LOCATION, TEXT_SPECIFY,
)

EVENT_FORMS = [fid for fid, t in FORM_TYPE_BY_ID.items() if t == "event_log"]


def main(window_days: int = 90, show: int = 5):
    import os
    print(">>> diag_bench starting", flush=True)
    print(f"    DATA_BUCKET={os.environ.get('DATA_BUCKET')!r}", flush=True)
    print(f"    SUBMISSIONS_TABLE={os.environ.get('SUBMISSIONS_TABLE')!r}", flush=True)
    print(f"    AWS_PROFILE={os.environ.get('AWS_PROFILE')!r} AWS_REGION={os.environ.get('AWS_REGION')!r}", flush=True)
    print(f"    fetching {window_days}d of records (reading S3, may take a moment)...", flush=True)
    recs = fetch_clean_records(window_days=window_days)
    print(f"fetched {len(recs)} clean records over {window_days}d\n", flush=True)

    loading = []
    for r in recs:
        fid = str(r.get("form_id") or _norm(r).get("form_id") or "")
        if fid not in EVENT_FORMS:
            continue
        act = (_norm(r).get("activity") or "").strip().lower()
        if "loading" in act:
            loading.append(r)

    print(f"found {len(loading)} 'Loading Explosives' event records\n")
    if not loading:
        print("No loading events in this window — widen window_days or check activity label.")
        return

    print(f"pipeline is matching these exact labels:")
    print(f"  bench_location <- {TEXT_BENCH_LOCATION!r}")
    print(f"  specify        <- {TEXT_SPECIFY!r}\n")
    print("=" * 70)

    for i, r in enumerate(loading[:show]):
        sub = r.get("submission_id")
        schema = r.get("schema") or {}
        raw = r.get("raw_submission") or r.get("data") or {}
        tmap = _text_value_map(r)
        by_qid = _index_raw_by_qid(raw)
        print(f"\n[{i+1}] submission_id={sub}")
        print("  schema labels (qid -> text):")
        for qid, q in schema.items():
            if isinstance(q, dict) and (q.get("text") or "").strip():
                hit = any(k in (q.get("text") or "").lower() for k in ("bench", "specify", "location"))
                print(f"    {'>>' if hit else '  '} qid={q.get('qid', qid)!s:<6} text={q.get('text')!r}")
        print("  text-value map (label -> value):")
        for k, v in tmap.items():
            hit = any(t in k.lower() for t in ("bench", "specify", "location"))
            print(f"    {'>>' if hit else '  '} {k!r}: {v!r}")
        print(f"  raw keys (first 25): {list(raw.keys())[:25]}")
        print(f"  by_qid keys: {sorted(by_qid.keys())}")
        print("-" * 70)


if __name__ == "__main__":
    wd = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    try:
        main(window_days=wd)
    except Exception:
        import traceback
        print("\n!!! diag_bench failed:", flush=True)
        traceback.print_exc()
        sys.exit(1)
