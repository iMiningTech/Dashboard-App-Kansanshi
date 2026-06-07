"""
Offline test for src/aws_source.py — proves the AWS-record reshape, the
schema-driven Pre-Start matrix explode, and the reused amalgamation, WITHOUT
touching AWS (fetch is a lazy import). Run from the repo root:

    python tests/test_aws_source.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.aws_source import build_outputs, explode_prestart, build_frames

CONFIG = load_config(str(ROOT / "config" / "mappings.yaml"))

# --- realistic records (matrix structure mirrors a real Pre-Start submission) ---
RECORDS = [
    {  # Shift START
        "form_id": "260905029221954", "submission_id": "S1", "received_at": "2026-04-01T06:00:00Z",
        "normalized_submission": {"operator": "Justin James", "fleet_no": "AFBM129",
                                  "submitted_at": "2026-04-01T06:00", "shift_event": "START"},
        "schema": {}, "raw_submission": {},
    },
    {  # Shift END
        "form_id": "260905029221954", "submission_id": "S2", "received_at": "2026-04-01T14:00:00Z",
        "normalized_submission": {"operator": "Justin James", "fleet_no": "AFBM129",
                                  "submitted_at": "2026-04-01T14:00", "shift_event": "END"},
        "schema": {}, "raw_submission": {},
    },
    {  # Event Log (within shift) — extra fields come from schema-text lookup
        "form_id": "260804815809967", "submission_id": "E1", "received_at": "2026-04-01T09:00:00Z",
        "normalized_submission": {"operator": "Justin James", "fleet_no": "AFBM129",
                                  "submitted_at": "2026-04-01T09:00", "activity": "Refueling"},
        "schema": {
            "7": {"qid": "7", "type": "control_textbox", "text": "Breakdown Category:"},
            "8": {"qid": "8", "type": "control_textbox", "text": "Additional Information (Optional):"},
        },
        "raw_submission": {"q7_cat": "Mechanical", "q8_info": "belt snapped"},
    },
    {  # Toolbox Talk
        "form_id": "261247755437969", "submission_id": "T1", "received_at": "2026-04-01T07:00:00Z",
        "normalized_submission": {"operator": "Justin James", "fleet_no": "AFBM129",
                                  "submitted_at": "2026-04-01T07:00"},
        "schema": {"5": {"qid": "5", "type": "control_textbox", "text": "Questions Or Concerns (Optional):"}},
        "raw_submission": {"q5_q": "Discussed wet roads"},
    },
    {  # Pre-Start with a control_matrix (IN CAB CHECKS, 3 items)
        "form_id": "260804512261953", "submission_id": "PS1", "received_at": "2026-04-01T05:30:00Z",
        "normalized_submission": {"operator": "Justin James", "fleet_no": "AFBM129",
                                  "submitted_at": "2026-04-01T05:30"},
        "schema": {"6": {"qid": "6", "type": "control_matrix", "text": "IN CAB CHECKS",
                         "mrows": "Cab clean\t\t\t|Horn works\t\t\t|Mirrors intact\t\t\t"}},
        "raw_submission": {"q6_inCab": [["FAULT", "F12", "loose items"], ["OK", "", ""], ["OK", "", ""]]},
    },
]


def check(name, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    assert cond, name


def main():
    print("build_frames:")
    shift, event, toolbox = build_frames(RECORDS, CONFIG)
    check("1 shift START + 1 END", len(shift) == 2 and set(shift["shift_event_type"]) == {"START", "END"})
    check("event has activity_type/category/detail",
          event.iloc[0]["activity_type"] == "Refueling"
          and event.iloc[0]["activity_category"] == "Mechanical"
          and event.iloc[0]["activity_detail"] == "belt snapped")
    check("toolbox detail mapped", toolbox.iloc[0]["activity_detail"] == "Discussed wet roads")

    print("explode_prestart:")
    ps = explode_prestart(RECORDS, CONFIG)
    check("3 checklist rows", len(ps) == 3)
    check("category + items", list(ps["checklist_item"]) == ["Cab clean", "Horn works", "Mirrors intact"]
          and set(ps["checklist_category"]) == {"IN CAB CHECKS"})
    check("fault flagged on FAULT row", bool(ps.iloc[0]["fault_flag"]) is True
          and ps.iloc[0]["fault_number"] == "F12" and ps.iloc[0]["comment"] == "loose items")
    check("OK rows not flagged", bool(ps.iloc[1]["fault_flag"]) is False)

    print("build_outputs (full amalgamation):")
    timeline, prestart, exceptions = build_outputs(RECORDS, CONFIG)
    acts = list(timeline["activity_type"])
    check("timeline has Shift Start/End", "Shift Start" in acts and "Shift End" in acts)
    check("timeline has Refueling event", "Refueling" in acts)
    check("timeline has Toolbox Talk", "Toolbox Talk" in acts)
    check("durations computed (numeric col present)", "duration_minutes" in timeline.columns)
    check("prestart has 3 rows", len(prestart) == 3)
    check("output columns match CSV contract",
          set(["session_id", "mmu_id", "operator_name", "activity_type", "duration_minutes"]).issubset(timeline.columns))

    print(f"\nAll checks passed. timeline={len(timeline)} prestart={len(prestart)} exceptions={len(exceptions)}")


if __name__ == "__main__":
    main()
