# MMU Operations CSV Normalizer
## Orica / Kansanshi — Dashboard Data Pipeline

Processes Jotform CSV exports into clean, dashboard-ready CSVs for Retool or any BI tool.

---

## Folder structure

```
project/
├── input/                  ← Place your Jotform CSV exports here
├── output/                 ← Generated output files (created on first run)
├── config/
│   └── mappings.yaml       ← Column mappings, aliases, and settings
└── src/
    ├── normalize.py        ← Main entry point
    ├── inspector.py        ← --inspect mode
    ├── loader.py           ← CSV loading and mapping
    ├── sessions.py         ← Shift session builder
    ├── timeline.py         ← Activity timeline and duration calculation
    ├── prestart.py         ← Pre-start checklist normalizer
    ├── quality.py          ← Data quality exception collector
    ├── config.py           ← Config loader
    └── utils.py            ← Shared utilities
```

---

## Requirements

Python 3.9+ and the packages in `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## Quick start

### Step 1 — Drop your CSVs in `/input`

Place all four Jotform exports in the `input/` folder:

| Source | What it is |
|---|---|
| Shift log | Operators log in/out of a shift and assign themselves to an MMU |
| Event log | Operational activities logged against an MMU during the shift |
| Toolbox talk | Daily safety talk log — becomes an activity event in the timeline |
| Pre-start checklist | MMU inspection — normalized separately into its own report |

Filenames don't need to match exactly — the tool detects source type from the filename.
Useful keywords in filenames: `shift`, `event`, `toolbox`, `prestart`.

### Step 2 — Inspect and generate the config

```bash
python src/normalize.py --inspect
```

This will:
- Print every CSV filename and all its column headers
- Generate `config/mappings.yaml` with auto-detected column mappings

### Step 3 — Review and fix the config

Open `config/mappings.yaml` and verify the mappings under each source.
Each entry looks like:

```yaml
sources:
  event_log:
    filename: my_event_log.csv
    columns:
      operator_name: "Operator Name"   # canonical field: your actual column header
      mmu_id: "MMU"
      timestamp: "Submission Time"
      activity_type: "Activity"
      activity_category: "Category"
      activity_detail: "Detail / Notes"
```

Set any unmapped field to `null` to leave it blank in the output.

### Step 4 — Add aliases (optional but recommended)

If your data has inconsistent MMU names or operator names, add them to the alias tables:

```yaml
mmu_aliases:
  "Truck 1": "MMU-001"
  "truck1":  "MMU-001"
  "MMU1":    "MMU-001"

operator_aliases:
  "J Smith": "John Smith"
  "john s":  "John Smith"
```

### Step 5 — Run normalization

```bash
python src/normalize.py --run
```

Add `-v` for verbose/debug output:

```bash
python src/normalize.py --run -v
```

---

## Output files

All outputs are written to `output/`.

### `normalized_activity_timeline.csv`

One row per activity event, chronologically sorted within each shift session.

| Column | Description |
|---|---|
| `session_id` | Unique shift session identifier |
| `mmu_id` | Normalized MMU / truck ID |
| `operator_name` | Normalized operator name |
| `source_table` | Which CSV the event came from |
| `activity_type` | `Shift Start`, `Toolbox Talk`, event type, or `Shift End` |
| `activity_category` | Category grouping |
| `activity_detail` | Free-text detail / notes |
| `start_timestamp` | Event start time |
| `end_timestamp` | Derived end time (= next event's start) |
| `duration_minutes` | Time spent on this activity |
| `reporting_date` | Date of the shift (for daily grouping) |
| `shift_start_timestamp` | Session shift start |
| `shift_end_timestamp` | Session shift end |
| `session_match_method` | How the event was matched to its session |
| `is_exception` | `True` if a data quality flag was raised |
| `exception_reason` | Description of the data quality issue |

**Dashboard use cases:**
- MMU utilization by date range → group by `mmu_id`, `reporting_date`, sum `duration_minutes`
- Activity breakdown by MMU → group by `mmu_id`, `activity_type`
- Average time per activity → group by `activity_type`, mean `duration_minutes`
- Missing logout report → filter `is_exception = True`, `exception_reason` contains "Missing Shift End"
- Operator activity timeline → filter by `operator_name`, sort by `start_timestamp`
- Daily shift summary → group by `reporting_date`, `mmu_id`, `operator_name`

### `normalized_prestart_report.csv`

Long-format pre-start checklist — one row per MMU / inspection / checklist item.

| Column | Description |
|---|---|
| `mmu_id` | Normalized MMU ID |
| `operator_name` | Operator who completed the check |
| `inspection_timestamp` | When the form was submitted |
| `reporting_date` | Date of the inspection |
| `checklist_item` | The checklist item column name |
| `response` | The operator's response |
| `fault_flag` | `True` if the response matched a fault keyword |
| `comments` | Any additional comments |
| `source_row_index` | Row number in the original CSV |
| `source_file` | Original filename |

### `data_quality_exceptions.csv`

All rows or events that raised a data quality flag.

| Column | Description |
|---|---|
| `source_table` | Which source CSV the issue came from |
| `source_row_index` | Row index in the original CSV |
| `exception_reason` | Human-readable description of the issue |
| `field` | The specific field that caused the issue |
| `session_id` | Session context (if matched) |
| `mmu_id` / `operator_name` / `timestamp` | Row context |

### `normalize.log`

Full processing log written to `output/normalize.log` on every run.

---

## Config reference (`config/mappings.yaml`)

```yaml
settings:
  timezone: "Africa/Lusaka"           # IANA tz name, or null
  max_activity_duration_minutes: 240  # Flag activities longer than this
  default_shift_end_if_missing: "17:00"  # Assume shift ends at this time if no Shift End logged

sources:
  <source_name>:
    filename: my_file.csv             # File in /input
    columns:
      <canonical_field>: "Original Column Header"

mmu_aliases:
  "Old Name": "Canonical Name"

operator_aliases:
  "Old Name": "Canonical Name"

fault_keywords:           # Pre-start response keywords that flag a fault
  - fail
  - no
  - defect
```

---

## Re-running after config changes

Just run `--run` again — it overwrites the output files each time.

```bash
python src/normalize.py --run
```

Run `--inspect` again if you add new CSV files to `/input`.

---

## Troubleshooting

**"Config not found"** — run `--inspect` first.

**"Source file not found"** — check that the filename in `mappings.yaml` matches the file in `/input/` exactly (case-sensitive on some systems).

**All durations are `null`** — check that `timestamp` / `shift_start_timestamp` columns are mapped correctly and contain parseable dates.

**Too many exceptions** — check `data_quality_exceptions.csv` for patterns. Common causes: wrong column mapped for `mmu_id`, timestamp column not mapped, or MMU names in event_log don't match MMU names in shift_log (add `mmu_aliases`).
