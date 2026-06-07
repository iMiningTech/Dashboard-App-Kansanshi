# Jotform → Dashboard Data Context

**Project:** Orica / Kansanshi — MMU Operations Dashboard
**Purpose of this doc:** Context for the new API project that will stream Jotform submissions into AWS. It documents (a) the four Jotform entry points/forms we collect, (b) the shape of each, and (c) how the current batch pipeline amalgamates them into dashboard-ready data — so the API can be designed with the eventual data storage/structure in mind.

> **Today this is a batch process.** Operators fill in Jotform forms; we periodically export CSVs, drop them in `/input`, and run a Python normalizer (`src/normalize.py`) that produces three dashboard CSVs. The API project's goal is to replace the manual CSV export/run step with a streaming ingest into AWS. The amalgamation logic below is the part that matters most for storage design — it's not a trivial passthrough.

---

## 1. The four Jotform entry points

There are **four separate Jotform forms**. Each is a distinct submission stream. All four share a small set of common identity fields, then diverge.

| # | Form (source) | What it captures | One submission = | Internal source key |
|---|---|---|---|---|
| 1 | **Shift Start / End Log** | An operator logging the start OR end of a shift on a given MMU | one **event** (a START *or* an END, not both) | `shift_log` |
| 2 | **Event Log** | An operational activity logged against an MMU during a shift (breakdowns, tasks, etc.) | one **activity event** | `event_log` |
| 3 | **Toolbox Talk Log** | The daily safety talk | one **safety event** | `toolbox_talk` |
| 4 | **MMU Pre-Start Checklist** | A full pre-shift MMU inspection (many checklist items in one submission) | one **inspection** (wide row, many items) | `prestart_checklist` |

### Common identity fields (present on all forms)
These are the join keys that tie the streams together. **Exact Jotform column labels in parentheses** (current as of the 2026-06-01 export):

- **Operator name** — `"Full Name"`
- **MMU / fleet number** — `"Fleet No:"`
- **Timestamp** — `"Date"` (this is the **user-entered** time of the event, not the Jotform submission time — see the gotcha in §4)

### Per-form specific fields

**1. Shift Start / End Log (`shift_log`)**
- `"Shift Start or End?"` — the discriminator. Values are `START` / `Start` or `END` / `End`.
- Critically, **a shift is two separate submissions**: one START row and one END row. They are *not* linked at source — the pipeline pairs them (see §3).

**2. Event Log (`event_log`)**
- `"What Are You Logging:"` → activity type
- `"Breakdown Category:"` → activity category
- `"Additional Information (Optional):"` → free-text detail
- (also a `"Specify:"` free-text field, currently not mapped)

**3. Toolbox Talk Log (`toolbox_talk`)**
- `"Questions Or Concerns (Optional):"` → free-text detail
- Otherwise just the common identity fields. Every submission becomes a single "Toolbox Talk" activity in the timeline.

**4. MMU Pre-Start Checklist (`prestart_checklist`)**
- This form is **wide**: each checklist item is a group of three columns following the pattern:
  ```
  "CATEGORY >> ITEM DESCRIPTION >> STATUS"
  "CATEGORY >> ITEM DESCRIPTION >> FAULT NO."
  "CATEGORY >> ITEM DESCRIPTION >> Comment"
  ```
- One submission can contain dozens of these triples. The pipeline auto-detects them (no need to enumerate items) by finding every `>> STATUS` column and locating its paired `FAULT NO.` / `Comment` columns.
- Other columns present (engine hours, kilometers, signature, photos, submission metadata) are treated as system/metadata and ignored as checklist items.

> **For the API:** if Jotform sends webhook payloads per submission, each of the four forms will need its own field mapping. The pre-start form especially: its payload is wide and item columns are dynamic. Consider whether the API should explode pre-start items into long rows at ingest, or store the raw submission and explode downstream (the current pipeline explodes to long format — see §3.4).

---

## 2. Why mapping is config-driven (and what this means for the API)

The exact Jotform column labels **change between exports** (and would change if the form is edited). The batch pipeline never hardcodes column names — it uses a config file, [config/mappings.yaml](config/mappings.yaml), that maps canonical field names → the actual Jotform header text. A `--inspect` mode auto-detects likely mappings by keyword heuristics, and a human confirms them.

Canonical fields the pipeline normalizes everything down to:

- `operator_name`, `mmu_id`, `timestamp` (common)
- `shift_event_type` (shift log only)
- `activity_type`, `activity_category`, `activity_detail` (event log)
- `inspection_timestamp` + dynamic checklist items (pre-start)

There are also **alias tables** (`mmu_aliases`, `operator_aliases`) to fold inconsistent free-text spellings (e.g. `"Truck 1"`, `"afbm 138"` → `"AFBM138"`) into one canonical ID. Operators type these by hand, so the same MMU/person appears under several spellings.

> **For the API / storage design:** the canonical field set above is effectively the target schema. The label→canonical mapping and the alias normalization are business logic that must live *somewhere* — either in the API ingest layer or as a transform step in AWS. They can't be skipped: without alias normalization the join keys (`mmu_id`, `operator_name`) won't line up across streams.

---

## 3. How the datasets are amalgamated

This is the core logic the API/storage design should be aware of. The four streams are **not** simply concatenated — three of them are woven into a single chronological **activity timeline** keyed by shift session, and the fourth (pre-start) is normalized into its own long-format report.

### 3.1 Build shift sessions (from `shift_log`)
- START and END rows are **paired** into sessions. For each START, find the best unused END where:
  1. same `mmu_id`,
  2. END timestamp is after START timestamp,
  3. prefer the same calendar date, and take the **earliest** valid END (so a shift doesn't swallow the next one),
  4. fall back to the next END after START (handles shifts crossing midnight).
- Each session gets a generated `session_id` and a `reporting_date` (the START date).
- Unmatched STARTs (no END) and unmatched ENDs (no START) are flagged as **data quality exceptions**, not dropped.

### 3.2 Match events to sessions (`event_log` + `toolbox_talk`)
Every event row is assigned to a session by:
1. **Window match** — same `mmu_id` and the event timestamp falls between the session's shift start and end. (If several windows match, pick the closest start.)
2. **Date fallback** — same `mmu_id` + same date, if no window match.
3. **None** — flagged as a quality exception ("No matching shift session").

If an event has no operator name, it **inherits** the operator from its matched session.

### 3.3 Assemble the timeline + derive durations
- Synthetic `Shift Start` and `Shift End` activity rows are generated for each session as boundary markers.
- All event sources are concatenated and sorted: `session_id → mmu_id → timestamp`, giving `Shift Start → …events… → Shift End`.
- **Durations are derived, not recorded.** Jotform captures only event timestamps. Each event's `duration_minutes` = (next event's start) − (this event's start). The last event runs to shift end (or is capped / flagged).
- Guard rails, all surfaced as exceptions:
  - Negative durations (out-of-order/duplicate timestamps) → set to 0, flagged.
  - Durations over `max_activity_duration_minutes` (default 240) → flagged.
  - Missing shift end → duration capped (or extended to a configurable default shift-end time), flagged.

> **This is the single most important thing for storage design:** activity duration is a *computed* field that depends on the **next event in the same session**. You cannot compute a row's duration from that row alone — you need the ordered set of events for the whole session. A pure event-at-a-time streaming insert will produce rows with null/unknown duration until the following event arrives. Options for the API/AWS side: (a) store raw events and compute durations in a downstream/batch view, or (b) recompute affected session durations on each new event. Don't bake duration into the raw event record at ingest.

### 3.4 Normalize pre-start (`prestart_checklist`)
- Independent of the timeline. Each wide inspection row is **exploded to long format**: one output row per (MMU, inspection, checklist item) with `status`, `fault_number`, `comment`.
- A `fault_flag` is set if the status text matches any fault keyword (`fault`, `fail`, `defect`, `broken`, `damaged`, `missing`, `leak`, `cracked`).

### 3.5 Data quality is a first-class output
Nothing is silently dropped. Every anomaly (missing IDs, unmatched shifts, bad timestamps, implausible durations) is written to a dedicated exceptions table with source file + row index for traceability. The API/AWS pipeline should preserve this principle — keep provenance (which form, which submission) and capture rejects rather than discarding them.

---

## 4. Gotchas worth carrying into the API design

1. **Timestamp is user-entered, not submission time.** The mapped `timestamp`/`Date` is what the operator typed, which can be wrong, missing, or unparseable. Jotform *also* has a true submission timestamp — the API will have direct access to it and should probably keep **both** (user-entered for shift logic, system submission time for audit/ordering).
2. **A shift = two independent submissions** (START and END) that aren't linked at source. Pairing is inferred. With a streaming API, a START may arrive hours before its END — session records are inherently open/incomplete until the END lands.
3. **MMU and operator are free-text** → require alias normalization to join reliably across streams.
4. **Pre-start forms are wide and dynamic** — item columns change if the form is edited. Detection is pattern-based (`>> STATUS`), not a fixed list. The API mapping must tolerate added/removed checklist items.
5. **Column labels drift between exports.** The current mapping (e.g. `"Fleet No:"`, `"What Are You Logging:"`) is correct for the 2026-06-01 export but is configuration, not a contract. Jotform's webhook payload uses field IDs/qids which are more stable than display labels — worth using those as the join key in the API rather than the display text.

---

## 5. Target output shape (what the dashboard consumes today)

Three CSVs, which the streaming pipeline will ultimately need to reproduce (as tables/views in AWS):

1. **`normalized_activity_timeline.csv`** — one row per activity event, with `session_id`, `mmu_id`, `operator_name`, `source_table`, `activity_type/category/detail`, `start_timestamp`, `end_timestamp`, `duration_minutes`, `reporting_date`, shift-window context, `session_match_method`, and `is_exception` / `exception_reason`. *This is the primary dashboard dataset.*
2. **`normalized_prestart_report.csv`** — long-format checklist: one row per (MMU, inspection, item) with `status`, `fault_number`, `comment`, `fault_flag`.
3. **`data_quality_exceptions.csv`** — every flagged anomaly with source provenance.

Full column reference lives in [README.md](README.md).

---

## 6. Reference — current pipeline code

For anyone on the API project who wants to see the exact amalgamation logic:

| Concern | File |
|---|---|
| Entry point / orchestration | [src/normalize.py](src/normalize.py) |
| Column mapping + alias normalization | [src/loader.py](src/loader.py) |
| Auto-detect form type & columns | [src/inspector.py](src/inspector.py) |
| Shift session pairing & event→session matching | [src/sessions.py](src/sessions.py) |
| Timeline assembly + duration derivation | [src/timeline.py](src/timeline.py) |
| Pre-start wide→long explode + fault flags | [src/prestart.py](src/prestart.py) |
| Quality exception collection | [src/quality.py](src/quality.py) |
| Live config (field mappings, aliases, settings) | [config/mappings.yaml](config/mappings.yaml) |
