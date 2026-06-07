# Dashboard on AWS — setup

The dashboard can read from the live JotForm→AWS pipeline instead of the batch
CSVs. Toggle with `DATA_SOURCE` (`aws` | `csv`). `src/aws_source.py` fetches a
rolling window of submissions, reshapes them into the same per-form frames the
amalgamation already uses, and reuses `build_sessions`/`build_timeline`/
`calculate_durations` + a schema-driven Pre-Start exploder to emit the same
three datasets the widgets consume. No widget changes.

## 1. Create a read-only IAM user (prod account `432046692351`)

Run with an admin profile on the prod account:

```bash
cd <dashboard repo>
aws iam create-user --user-name kansanshi-dashboard-readonly --profile imining-dev
aws iam put-user-policy --user-name kansanshi-dashboard-readonly \
  --policy-name dashboard-readonly \
  --policy-document file://aws/dashboard-readonly-policy.json --profile imining-dev
aws iam create-access-key --user-name kansanshi-dashboard-readonly --profile imining-dev
```

The last command prints an `AccessKeyId` + `SecretAccessKey` — these are read-only
(S3 GetObject/List on the data bucket + DynamoDB read on the three tables, nothing
else). Save them in 1Password and use them below.

## 2. Configure secrets

Local:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # gitignored
# fill in access_key_id / secret_access_key, set source = "aws"
pip install -r requirements.txt
streamlit run dashboard.py
```

Streamlit Cloud: open the app → Settings → Secrets, paste the same TOML
(`[data]` + `[aws]` blocks). `boto3` is in `requirements.txt`, so Cloud installs it.
Push to GitHub as usual and it redeploys.

## 3. How it behaves

- Default loads the last **7 days** (`window_days`), amalgamated on read, cached 5 min.
- Filtering within the loaded window is instant (slices cached data); widening the
  window triggers a short reload.
- Live MMU/operator status comes from `current_mmu` / `current_session` (real-time).
- `DATA_SOURCE=csv` (or unset) keeps the original batch behaviour unchanged.

## 4. Later: monthly precompute

`src/aws_source.load_from_aws(window_days=…)` is the single entry point. A
scheduled Lambda can call it with a month-long window once per month and write
the three outputs to S3 for fast historical views — no dashboard changes needed.

## Validate offline

```bash
python tests/test_aws_source.py   # proves reshape + Pre-Start explode + amalgamation
```
