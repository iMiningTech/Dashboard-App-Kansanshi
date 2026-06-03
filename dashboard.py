#!/usr/bin/env python3
"""
MMU Operations Dashboard — Kansanshi
Interactive operations reporting dashboard.

Run:
    py -m streamlit run dashboard.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MMU Operations — Kansanshi",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        /* ── Hide Streamlit chrome ── */
        #MainMenu                      {visibility: hidden;}
        footer                         {visibility: hidden;}
        [data-testid="stToolbar"]      {display: none;}
        [data-testid="stDecoration"]   {display: none;}
        [data-testid="stStatusWidget"] {display: none;}

        /* Force sidebar open — hide the collapse button */
        [data-testid="stSidebarCollapseButton"] {display: none !important;}

        /* ── Sidebar skin — white + Orica blue ── */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 3px solid #0082CA;
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label {
            color: #003087 !important;
        }
        [data-testid="stSidebar"] hr {
            border-color: #0082CA !important;
            opacity: 0.4;
        }
        /* Multiselect selected-item tags */
        [data-testid="stSidebar"] [data-baseweb="tag"] {
            background-color: #0082CA !important;
            border: none !important;
        }
        [data-testid="stSidebar"] [data-baseweb="tag"] span {
            color: #FFFFFF !important;
        }
        /* Slider thumb dots */
        [data-testid="stSidebar"] [role="slider"] {
            background-color: #0082CA !important;
            border-color: #0082CA !important;
        }
        /* Slider filled track — Emotion class visible in inspector */
        [data-testid="stSidebar"] .e2ups023 > div {
            background: #0082CA !important;
            background-color: #0082CA !important;
        }
        /* Caption / small text */
        [data-testid="stSidebar"] small,
        [data-testid="stSidebar"] .stCaption {
            color: #003087 !important;
            opacity: 0.7;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Master colour palette ──────────────────────────────────────────────────────
# 15 visually distinct colours based on Tableau 10 + extras.
# Used for any categorical series that doesn't have a semantic mapping.
MASTER_PALETTE = [
    "#4E79A7",  # steel blue
    "#F28E2B",  # orange
    "#E15759",  # coral red
    "#76B7B2",  # teal
    "#59A14F",  # green
    "#EDC948",  # amber
    "#B07AA1",  # purple
    "#FF9DA7",  # pink
    "#9C755F",  # brown
    "#499894",  # dark teal
    "#D37295",  # rose
    "#86BCB6",  # light teal
    "#FABFD2",  # blush
    "#E8AC0F",  # gold
    "#BAB0AC",  # warm grey
]

def palette_map(categories) -> dict:
    """Assign a distinct master-palette colour to each unique category."""
    cats = list(dict.fromkeys(categories))   # preserve order, deduplicate
    return {c: MASTER_PALETTE[i % len(MASTER_PALETTE)] for i, c in enumerate(cats)}


# ── Semantic activity colours ─────────────────────────────────────────────────
# Grouped by meaning: productive = blue/teal, movement = green,
# idle/wait = grey/brown, maintenance = amber, safety/admin = orange,
# problems = red/rose.
ACTIVITY_COLOURS = {
    # Core productive work
    "Loading Explosives":        "#4E79A7",   # steel blue
    "FQMO - Dipping & Priming":  "#499894",   # dark teal
    "Reload":                    "#76B7B2",   # light teal
    # Movement
    "Travel":                    "#59A14F",   # green
    # Idle / waiting
    "Standby":                   "#BAB0AC",   # warm grey
    "Waiting For Explosives":    "#9C755F",   # brown
    "Waiting For Personnel":     "#B07AA1",   # purple
    # Maintenance / support
    "Refueling":                 "#EDC948",   # amber
    "Breakdown":                 "#E15759",   # coral red
    # Safety & admin
    "Toolbox Talk":              "#F28E2B",   # orange
    "Tool Box Meeting":          "#E8AC0F",   # gold
    "Unsafe Condition":          "#D37295",   # rose
    "Safety Violation":          "#E15759",   # red (same urgency as Breakdown)
    # Shift boundaries (shown in timeline only)
    "Shift Start":               "#86BCB6",   # pale teal
    "Shift End":                 "#FABFD2",   # blush
}

# Checklist category colours — four distinct, non-activity colours
CATEGORY_COLOURS = {
    "IN CAB CHECKS":     "#4E79A7",   # blue
    "EXTERNAL CHECKS":   "#F28E2B",   # orange
    "QUALITY":           "#59A14F",   # green
    "BEFORE DRIVING OFF":"#E15759",   # red
}

# Shift performance bucket colours
BUCKET_COLOURS = {
    "Productive":   "#59A14F",   # green
    "Movement":     "#4E79A7",   # blue
    "Downtime":     "#E15759",   # red
    "Maintenance":  "#EDC948",   # amber
    "Safety/Admin": "#F28E2B",   # orange
}


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    ts_cols = ["start_timestamp", "end_timestamp", "shift_start_timestamp", "shift_end_timestamp"]
    timeline = pd.read_csv(OUTPUT_DIR / "normalized_activity_timeline.csv",
                           parse_dates=ts_cols, low_memory=False)
    prestart = pd.read_csv(OUTPUT_DIR / "normalized_prestart_report.csv",
                           parse_dates=["inspection_timestamp"], low_memory=False)
    exceptions = pd.read_csv(OUTPUT_DIR / "data_quality_exceptions.csv", low_memory=False)

    timeline["reporting_date"] = pd.to_datetime(timeline["reporting_date"], errors="coerce").dt.date
    prestart["reporting_date"] = pd.to_datetime(prestart["reporting_date"], errors="coerce").dt.date
    return timeline, prestart, exceptions


with st.spinner("Loading data…"):
    timeline_raw, prestart_raw, exceptions_raw = load_data()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    logo_path = PROJECT_ROOT / "assets" / "orica_logo.png"
    if logo_path.exists():
        st.image(str(logo_path), width=140)
    st.markdown("## Kansanshi MMU Ops")
    st.markdown("---")

    all_dates = sorted(d for d in timeline_raw["reporting_date"].dropna().unique())
    all_mmus  = sorted(timeline_raw["mmu_id"].dropna().unique())

    st.markdown("### Filters")
    if len(all_dates) >= 2:
        date_range = st.slider(
            "Date range",
            min_value=all_dates[0],
            max_value=all_dates[-1],
            value=(all_dates[0], all_dates[-1]),
        )
    else:
        date_range = (all_dates[0], all_dates[-1]) if all_dates else (None, None)

    selected_mmus = st.multiselect("MMUs", all_mmus, default=all_mmus, placeholder="All MMUs")
    if not selected_mmus:
        selected_mmus = all_mmus

    st.markdown("---")
    st.caption(f"{len(timeline_raw):,} activity records · {len(prestart_raw):,} inspection records")


# ── Filters ───────────────────────────────────────────────────────────────────
def apply_filters(df):
    mask = (
        df["reporting_date"].notna()
        & (df["reporting_date"] >= date_range[0])
        & (df["reporting_date"] <= date_range[1])
        & (df["mmu_id"].isin(selected_mmus))
    )
    return df[mask].copy()


tl = apply_filters(timeline_raw)
ps = prestart_raw[
    prestart_raw["reporting_date"].notna()
    & (prestart_raw["reporting_date"] >= date_range[0])
    & (prestart_raw["reporting_date"] <= date_range[1])
    & (prestart_raw["mmu_id"].isin(selected_mmus))
].copy()


# ── Derived data ──────────────────────────────────────────────────────────────
sessions_with_end = set(tl[tl["activity_type"] == "Shift End"]["session_id"].dropna())

session_summary = (
    tl[tl["activity_type"] == "Shift Start"]
    .groupby("session_id", as_index=False)
    .agg(
        mmu_id=("mmu_id", "first"),
        operator_name=("operator_name", "first"),
        reporting_date=("reporting_date", "first"),
        shift_start=("start_timestamp", "first"),
        shift_end=("shift_end_timestamp", "first"),
    )
)
session_summary["clocked_out"] = session_summary["session_id"].isin(sessions_with_end)
sessions_no_end = session_summary[~session_summary["clocked_out"]].copy()

activity_tl = tl[~tl["activity_type"].isin(["Shift Start", "Shift End"])].copy()
activity_tl["duration_hours"] = activity_tl["duration_minutes"].clip(upper=240) / 60


# ── KPI cards ─────────────────────────────────────────────────────────────────
st.title("MMU Operations Dashboard")
st.markdown(f"**Kansanshi Mining — data period: {date_range[0]} to {date_range[1]}**")
st.markdown("---")

# ── Site Status ───────────────────────────────────────────────────────────────
st.markdown("### Site Status")
st.caption(f"Last logged activity per MMU — most recent within selected date range.")

if tl.empty:
    st.info("No data for the selected filters.")
else:
    latest_per_mmu = (
        tl.dropna(subset=["start_timestamp"])
        .sort_values("start_timestamp", ascending=False)
        .groupby("mmu_id", as_index=False)
        .first()
    )[["mmu_id", "operator_name", "activity_type", "start_timestamp", "session_id", "reporting_date"]]
    latest_per_mmu["active"] = ~latest_per_mmu["session_id"].isin(sessions_with_end)

    prestart_keys = set(zip(prestart_raw["mmu_id"], prestart_raw["reporting_date"]))
    latest_per_mmu["has_prestart"] = latest_per_mmu.apply(
        lambda r: (r["mmu_id"], r["reporting_date"]) in prestart_keys, axis=1
    )
    latest_per_mmu = latest_per_mmu.sort_values("mmu_id").reset_index(drop=True)

    cols_per_row = 4
    for i in range(0, len(latest_per_mmu), cols_per_row):
        chunk = latest_per_mmu.iloc[i:i + cols_per_row]
        card_cols = st.columns(cols_per_row)
        for card_col, (_, row) in zip(card_cols, chunk.iterrows()):
            with card_col:
                with st.container(border=True):
                    ts = row["start_timestamp"]
                    ts_str = ts.strftime("%H:%M · %d %b") if pd.notna(ts) else "—"
                    badge = "🟢 Active" if row["active"] else "⚫ Shift Ended"
                    prestart_badge = "" if row["has_prestart"] else " &nbsp; ⚠️ No Prestart"
                    st.markdown(f"**{row['mmu_id']}** &nbsp; {badge}{prestart_badge}")
                    st.markdown(f"👤 &nbsp; {row['operator_name'] or '—'}")
                    st.markdown(f"**{row['activity_type']}**")
                    st.caption(ts_str)

st.markdown("---")

total_sessions     = session_summary["session_id"].nunique()
active_mmus        = tl["mmu_id"].nunique()
missing_logout_n   = len(sessions_no_end)
missing_logout_pct = (missing_logout_n / total_sessions * 100) if total_sessions else 0
total_faults       = ps["fault_flag"].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Shift Sessions",     f"{total_sessions}")
k2.metric("Active MMUs",              f"{active_mmus}")
k3.metric("Missing Shift-End Logs",
          f"{missing_logout_n}",
          delta=f"{missing_logout_pct:.0f}% of sessions",
          delta_color="inverse")
k4.metric("Pre-start Faults Flagged", f"{int(total_faults)}")

st.markdown("---")


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_logout, tab_util, tab_prestart, tab_perf, tab_timeline = st.tabs([
    "🔴  Missing Shift-End Logs",
    "📊  MMU Utilization",
    "⚠️  Pre-start Faults",
    "⏱️  Shift Performance",
    "📅  Shift Timeline",
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — MISSING LOGOUTS
# ════════════════════════════════════════════════════════════════════════════════
with tab_logout:
    st.subheader("Operators who started a shift but did not log Shift End")
    st.markdown(
        "Each session below has a **Shift Start** with no corresponding **Shift End**. "
        "Without a logged end time, activity tracking is incomplete and utilization "
        "calculations for these sessions are estimates only."
    )

    col_a, col_b = st.columns([1, 1])

    with col_a:
        by_op = (
            sessions_no_end.groupby("operator_name")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=True)
        )
        op_colours = palette_map(by_op["operator_name"])
        fig_op = px.bar(
            by_op,
            x="count",
            y="operator_name",
            orientation="h",
            title="Missing Shift-End Logs by Operator",
            labels={"count": "Sessions without Shift End", "operator_name": "Operator"},
            color="operator_name",
            color_discrete_map=op_colours,
        )
        fig_op.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_op, use_container_width=True)

    with col_b:
        by_date = (
            sessions_no_end.groupby("reporting_date")
            .size()
            .reset_index(name="count")
            .sort_values("reporting_date")
        )
        date_colours = palette_map(by_date["reporting_date"].astype(str))
        fig_date = px.bar(
            by_date,
            x="reporting_date",
            y="count",
            title="Missing Shift-End Logs by Date",
            labels={"count": "Sessions without Shift End", "reporting_date": "Date"},
            color="reporting_date",
            color_discrete_map={str(k): v for k, v in date_colours.items()},
        )
        fig_date.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_date, use_container_width=True)

    st.markdown("#### Session detail")
    display_no_end = sessions_no_end[[
        "operator_name", "mmu_id", "reporting_date", "shift_start"
    ]].rename(columns={
        "operator_name": "Operator",
        "mmu_id":        "MMU",
        "reporting_date":"Date",
        "shift_start":   "Shift Start Time",
    }).sort_values(["Date", "MMU"])

    st.dataframe(display_no_end.reset_index(drop=True), use_container_width=True, height=300)

    if not sessions_no_end.empty:
        st.download_button(
            "⬇ Download missing shift-end report",
            display_no_end.to_csv(index=False).encode(),
            "missing_shift_end.csv", "text/csv",
        )


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — MMU UTILIZATION
# ════════════════════════════════════════════════════════════════════════════════
with tab_util:
    st.subheader("Time on task — by MMU and activity type")
    st.markdown(
        "Shows how time is distributed across operational activities for each truck. "
        "Durations are capped at 4 hours per event to prevent incomplete sessions from "
        "distorting the totals."
    )

    col_c, col_d = st.columns([3, 2])

    with col_c:
        util = (
            activity_tl.groupby(["mmu_id", "activity_type"])["duration_hours"]
            .sum()
            .reset_index()
            .sort_values("mmu_id")
        )
        # Fall back to master palette for any activity type not in the semantic map
        act_colour_map = {
            act: ACTIVITY_COLOURS.get(act, MASTER_PALETTE[i % len(MASTER_PALETTE)])
            for i, act in enumerate(util["activity_type"].unique())
        }
        fig_util = px.bar(
            util,
            x="mmu_id",
            y="duration_hours",
            color="activity_type",
            title="Total Activity Hours by MMU",
            labels={"mmu_id": "MMU", "duration_hours": "Hours", "activity_type": "Activity"},
            color_discrete_map=act_colour_map,
        )
        fig_util.update_layout(height=450, legend_title="Activity")
        st.plotly_chart(fig_util, use_container_width=True)

    with col_d:
        overall = (
            activity_tl.groupby("activity_type")["duration_hours"]
            .sum()
            .reset_index()
            .sort_values("duration_hours", ascending=False)
        )
        fig_donut = px.pie(
            overall,
            names="activity_type",
            values="duration_hours",
            title="Fleet-wide Activity Mix",
            hole=0.45,
            color="activity_type",
            color_discrete_map=act_colour_map,
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label")
        fig_donut.update_layout(height=450, showlegend=False)
        st.plotly_chart(fig_donut, use_container_width=True)

    daily = (
        activity_tl.groupby(["reporting_date", "activity_type"])["duration_hours"]
        .sum()
        .reset_index()
        .sort_values("reporting_date")
    )
    if not daily.empty:
        fig_trend = px.area(
            daily,
            x="reporting_date",
            y="duration_hours",
            color="activity_type",
            title="Daily Activity Hours Trend",
            labels={"reporting_date": "Date", "duration_hours": "Hours", "activity_type": "Activity"},
            color_discrete_map=act_colour_map,
        )
        fig_trend.update_layout(height=320, legend_title="Activity")
        st.plotly_chart(fig_trend, use_container_width=True)

    st.markdown("#### Hours by MMU and activity")
    pivot = (
        activity_tl.groupby(["mmu_id", "activity_type"])["duration_hours"]
        .sum().round(1).unstack(fill_value=0).reset_index()
    )
    pivot.columns.name = None
    st.dataframe(pivot, use_container_width=True, height=280)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — PRE-START FAULTS
# ════════════════════════════════════════════════════════════════════════════════
with tab_prestart:
    st.subheader("MMU Pre-Start Checklist — Fault Summary")
    st.markdown(
        "Checklist items flagged during daily pre-start inspections, broken down by "
        "category: **IN CAB CHECKS**, **EXTERNAL CHECKS**, **QUALITY**, and **BEFORE DRIVING OFF**."
    )

    faults     = ps[ps["fault_flag"]].copy()
    all_checks = ps.copy()

    col_e, col_f = st.columns([1, 1])

    with col_e:
        faults_by_mmu = (
            faults.groupby("mmu_id").size()
            .reset_index(name="fault_count")
            .sort_values("fault_count", ascending=True)
        )
        mmu_colours = palette_map(faults_by_mmu["mmu_id"])
        fig_mmu_fault = px.bar(
            faults_by_mmu,
            x="fault_count",
            y="mmu_id",
            orientation="h",
            title="Fault Flags by MMU",
            labels={"fault_count": "Fault Flags", "mmu_id": "MMU"},
            color="mmu_id",
            color_discrete_map=mmu_colours,
        )
        fig_mmu_fault.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig_mmu_fault, use_container_width=True)

    with col_f:
        faults_by_cat = (
            faults.groupby("checklist_category").size()
            .reset_index(name="fault_count")
            .sort_values("fault_count", ascending=False)
        )
        fig_cat = px.pie(
            faults_by_cat,
            names="checklist_category",
            values="fault_count",
            title="Faults by Checklist Category",
            hole=0.4,
            color="checklist_category",
            color_discrete_map=CATEGORY_COLOURS,
        )
        fig_cat.update_traces(textposition="outside", textinfo="percent+label")
        fig_cat.update_layout(height=380, showlegend=False)
        st.plotly_chart(fig_cat, use_container_width=True)

    st.markdown("#### Most frequently flagged checklist items")
    item_fault_rate = (
        all_checks.groupby(["checklist_category", "checklist_item"])
        .agg(total_checks=("fault_flag", "count"), fault_count=("fault_flag", "sum"))
        .reset_index()
    )
    item_fault_rate["fault_rate_pct"] = (
        item_fault_rate["fault_count"] / item_fault_rate["total_checks"] * 100
    ).round(1)
    item_fault_rate = (
        item_fault_rate[item_fault_rate["fault_count"] > 0]
        .sort_values("fault_count", ascending=False)
    )
    item_fault_rate["item_short"] = item_fault_rate["checklist_item"].str[:65] + "…"

    fig_items = px.bar(
        item_fault_rate.head(15),
        x="fault_count",
        y="item_short",
        color="checklist_category",
        orientation="h",
        title="Top 15 Most Flagged Items",
        labels={"fault_count": "Fault Count", "item_short": "", "checklist_category": "Category"},
        color_discrete_map=CATEGORY_COLOURS,
    )
    fig_items.update_layout(height=430, legend_title="Category", yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_items, use_container_width=True)

    st.markdown("#### Fault records")
    fault_detail = faults[[
        "mmu_id", "operator_name", "inspection_timestamp", "reporting_date",
        "checklist_category", "checklist_item", "status", "fault_number", "comment"
    ]].rename(columns={
        "mmu_id":               "MMU",
        "operator_name":        "Operator",
        "inspection_timestamp": "Inspection Time",
        "reporting_date":       "Date",
        "checklist_category":   "Category",
        "checklist_item":       "Item",
        "status":               "Status",
        "fault_number":         "Fault No.",
        "comment":              "Comment",
    }).sort_values(["Date", "MMU"])

    st.dataframe(fault_detail.reset_index(drop=True), use_container_width=True, height=320)

    if not fault_detail.empty:
        st.download_button(
            "⬇ Download fault records",
            fault_detail.to_csv(index=False).encode(),
            "prestart_faults.csv", "text/csv",
        )


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — SHIFT PERFORMANCE
# ════════════════════════════════════════════════════════════════════════════════
with tab_perf:
    st.subheader("Shift Start Times & Productive vs Downtime")

    ACTIVITY_BUCKET = {
        "Loading Explosives":        "Productive",
        "FQMO - Dipping & Priming":  "Productive",
        "Reload":                    "Productive",
        "Travel":                    "Movement",
        "Standby":                   "Downtime",
        "Waiting For Explosives":    "Downtime",
        "Waiting For Personnel":     "Downtime",
        "Refueling":                 "Maintenance",
        "Breakdown":                 "Maintenance",
        "Toolbox Talk":              "Safety/Admin",
        "Tool Box Meeting":          "Safety/Admin",
        "Unsafe Condition":          "Safety/Admin",
        "Safety Violation":          "Safety/Admin",
    }

    perf = session_summary.dropna(subset=["shift_start"]).copy()
    perf["start_hour_dec"] = perf["shift_start"].dt.hour + perf["shift_start"].dt.minute / 60
    perf["start_time_str"] = perf["shift_start"].dt.strftime("%H:%M")
    perf["date_str"] = perf["reporting_date"].astype(str)

    # ── Shift start times ─────────────────────────────────────────────────────
    st.markdown("### Shift Start Times")
    st.markdown(
        "Each point is one shift session. The Y-axis shows when the operator logged Shift Start — "
        "low = early start, high = late start."
    )

    op_start_colours = palette_map(perf["operator_name"])
    fig_starts = px.scatter(
        perf.sort_values("reporting_date"),
        x="date_str",
        y="start_hour_dec",
        color="operator_name",
        color_discrete_map=op_start_colours,
        hover_data={"start_time_str": True, "start_hour_dec": False, "date_str": False},
        labels={
            "date_str": "Date",
            "start_hour_dec": "Shift Start Time",
            "operator_name": "Operator",
            "start_time_str": "Start Time",
        },
        title="Shift Start Time by Operator and Date",
        height=420,
    )
    hour_ticks = list(range(4, 14))
    fig_starts.update_layout(
        yaxis=dict(
            tickvals=hour_ticks,
            ticktext=[f"{h:02d}:00" for h in hour_ticks],
            title="Start Time",
        )
    )
    st.plotly_chart(fig_starts, use_container_width=True)

    start_summary = (
        perf.groupby("operator_name")
        .agg(
            Sessions=("session_id", "count"),
            Earliest=("start_time_str", "min"),
            Latest=("start_time_str", "max"),
            avg_h=("start_hour_dec", "mean"),
        )
        .reset_index()
        .rename(columns={"operator_name": "Operator"})
    )
    start_summary["Avg Start"] = start_summary["avg_h"].apply(
        lambda h: f"{int(h):02d}:{int((h % 1) * 60):02d}"
    )
    st.dataframe(
        start_summary[["Operator", "Sessions", "Earliest", "Latest", "Avg Start"]],
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")

    # ── Productive vs Downtime ────────────────────────────────────────────────
    st.markdown("### Productive Time vs Downtime")
    st.markdown(
        "Activities grouped into: **Productive** (loading, FQMO, reload), "
        "**Movement** (travel), **Downtime** (standby, waiting), "
        "**Maintenance** (refueling, breakdown), **Safety/Admin** (toolbox talks). "
        "Dead Time shows unlogged minutes between Shift Start and the first logged activity."
    )

    bucketed = activity_tl.copy()
    bucketed["bucket"] = bucketed["activity_type"].map(ACTIVITY_BUCKET).fillna("Other")

    bucket_by_mmu = (
        bucketed.groupby(["mmu_id", "bucket"])["duration_hours"]
        .sum()
        .reset_index()
    )
    fig_buckets = px.bar(
        bucket_by_mmu,
        x="mmu_id",
        y="duration_hours",
        color="bucket",
        title="Time Breakdown by MMU",
        labels={"mmu_id": "MMU", "duration_hours": "Hours", "bucket": "Category"},
        color_discrete_map=BUCKET_COLOURS,
        height=420,
    )
    fig_buckets.update_layout(legend_title="Category")
    st.plotly_chart(fig_buckets, use_container_width=True)

    # ── Dead time (shift start → first logged activity) ───────────────────────
    st.markdown("#### Dead Time — Shift Start to First Logged Activity")
    st.markdown(
        "Time between logging Shift Start and the first activity entry. "
        "A large bar means the operator was on site but nothing was recorded."
    )

    first_acts = (
        activity_tl
        .groupby("session_id")["start_timestamp"]
        .min()
        .reset_index(name="first_activity_ts")
    )
    gap_df = perf.merge(first_acts, on="session_id", how="left")
    gap_df["dead_time_min"] = (
        (gap_df["first_activity_ts"] - gap_df["shift_start"])
        .dt.total_seconds() / 60
    ).clip(lower=0).round(1)
    gap_df["label"] = gap_df["operator_name"] + "  (" + gap_df["date_str"] + ")"
    gap_df = gap_df.dropna(subset=["dead_time_min"]).sort_values("dead_time_min", ascending=True)

    gap_colours = palette_map(gap_df["operator_name"])
    fig_gap = px.bar(
        gap_df,
        x="dead_time_min",
        y="label",
        color="operator_name",
        color_discrete_map=gap_colours,
        orientation="h",
        title="Dead Time per Shift Session (minutes from Shift Start to first activity)",
        labels={"dead_time_min": "Minutes", "label": "", "operator_name": "Operator"},
        height=max(350, len(gap_df) * 30),
    )
    fig_gap.update_layout(showlegend=False)
    st.plotly_chart(fig_gap, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 — SHIFT TIMELINE
# ════════════════════════════════════════════════════════════════════════════════
with tab_timeline:
    if len(selected_mmus) != 1:
        st.info("Select a **single MMU** in the sidebar to view the shift timeline.")
    else:
        mmu_single = selected_mmus[0]
        st.subheader(f"Shift Timeline — {mmu_single}")
        st.markdown(
            "Each bar represents one logged activity. The horizontal axis is wall-clock time "
            "from Shift Start to Shift End (or last logged event)."
        )

        mmu_tl = tl[tl["mmu_id"] == mmu_single].dropna(subset=["start_timestamp"])
        available_dates = sorted(mmu_tl["reporting_date"].dropna().unique())

        if not available_dates:
            st.info("No data for this MMU in the selected date range.")
        else:
            selected_day = st.selectbox(
                "Select date",
                options=available_dates,
                index=len(available_dates) - 1,
                format_func=str,
                key="timeline_date",
            )

            day_tl = mmu_tl[mmu_tl["reporting_date"] == selected_day].copy()

            # Reconstruct missing end timestamps from duration
            missing_end = day_tl["end_timestamp"].isna() & day_tl["duration_minutes"].notna()
            day_tl.loc[missing_end, "end_timestamp"] = (
                day_tl.loc[missing_end, "start_timestamp"]
                + pd.to_timedelta(day_tl.loc[missing_end, "duration_minutes"], unit="m")
            )
            day_tl = day_tl.dropna(subset=["end_timestamp"]).sort_values("start_timestamp")

            if day_tl.empty:
                st.info("No complete activity records for this day.")
            else:
                tl_colour_map = {
                    act: ACTIVITY_COLOURS.get(act, MASTER_PALETTE[i % len(MASTER_PALETTE)])
                    for i, act in enumerate(day_tl["activity_type"].unique())
                }

                fig_tl = px.timeline(
                    day_tl,
                    x_start="start_timestamp",
                    x_end="end_timestamp",
                    y="mmu_id",
                    color="activity_type",
                    color_discrete_map=tl_colour_map,
                    title=f"{mmu_single}  ·  {selected_day}",
                    labels={"activity_type": "Activity", "mmu_id": ""},
                    hover_data={
                        "start_timestamp": True,
                        "end_timestamp": True,
                        "duration_minutes": True,
                        "mmu_id": False,
                    },
                )
                fig_tl.update_layout(height=220, legend_title="Activity", xaxis_title="Time")
                st.plotly_chart(fig_tl, use_container_width=True)

                # Activity breakdown for the day
                st.markdown("#### Activity breakdown")
                breakdown = (
                    day_tl[~day_tl["activity_type"].isin(["Shift Start", "Shift End"])]
                    .groupby("activity_type")["duration_minutes"]
                    .sum()
                    .round(0)
                    .astype(int)
                    .reset_index()
                    .rename(columns={"activity_type": "Activity", "duration_minutes": "Minutes"})
                    .sort_values("Minutes", ascending=False)
                    .reset_index(drop=True)
                )
                st.dataframe(breakdown, hide_index=True, use_container_width=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "MMU Operations Dashboard · Kansanshi · "
    "Durations capped at 240 min per activity. Sessions without a logged Shift End are flagged."
)
