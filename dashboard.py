#!/usr/bin/env python3
"""
MMU Operations Dashboard — Kansanshi
Streamlit interactive demo for customer presentation.

Run:
    py -m streamlit run dashboard.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

# ── Colour palette ─────────────────────────────────────────────────────────────
COLOURS = {
    "blue":   "#4C9BE8",
    "orange": "#FF6B35",
    "green":  "#00BC70",
    "red":    "#E84C4C",
    "purple": "#9B59B6",
    "yellow": "#F1C40F",
}

# Activity colours — add more if needed
ACTIVITY_COLOURS = {
    "Shift Start":           "#5C6BC0",
    "Shift End":             "#26A69A",
    "Toolbox Talk":          "#FFA726",
    "Travel":                "#42A5F5",
    "Loading Explosives":    "#EF5350",
    "Reload":                "#AB47BC",
    "FQMO - Dipping & Priming": "#FF7043",
    "Standby":               "#78909C",
    "Breakdown":             "#E53935",
    "Refueling":             "#66BB6A",
    "Waiting For Explosives":"#EC407A",
    "Waiting For Personnel": "#FF8A65",
    "Tool Box Meeting":      "#FFCA28",
    "Unsafe Condition":      "#D32F2F",
    "Safety Violation":      "#B71C1C",
}


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    ts_cols = ["start_timestamp", "end_timestamp", "shift_start_timestamp", "shift_end_timestamp"]
    timeline = pd.read_csv(OUTPUT_DIR / "normalized_activity_timeline.csv", parse_dates=ts_cols, low_memory=False)
    prestart = pd.read_csv(OUTPUT_DIR / "normalized_prestart_report.csv", parse_dates=["inspection_timestamp"], low_memory=False)
    exceptions = pd.read_csv(OUTPUT_DIR / "data_quality_exceptions.csv", low_memory=False)

    # Normalise reporting_date to date type
    timeline["reporting_date"] = pd.to_datetime(timeline["reporting_date"], errors="coerce").dt.date
    prestart["reporting_date"] = pd.to_datetime(prestart["reporting_date"], errors="coerce").dt.date
    return timeline, prestart, exceptions


with st.spinner("Loading data…"):
    timeline_raw, prestart_raw, exceptions_raw = load_data()


# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚛 Kansanshi MMU Ops")
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
    st.caption(f"Data from `output/` folder")
    st.caption(f"{len(timeline_raw):,} timeline rows · {len(prestart_raw):,} inspection rows")


# ── Apply filters ─────────────────────────────────────────────────────────────
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
# Sessions — which ones have a Shift End?
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

# Activity hours (exclude synthetic boundary events)
activity_tl = tl[~tl["activity_type"].isin(["Shift Start", "Shift End"])].copy()
activity_tl["duration_hours"] = activity_tl["duration_minutes"].clip(upper=240) / 60

# ── KPI cards ─────────────────────────────────────────────────────────────────
st.title("MMU Operations Dashboard")
st.markdown(f"**Kansanshi Mining — data period: {date_range[0]} → {date_range[1]}**")
st.markdown("---")

total_sessions    = session_summary["session_id"].nunique()
active_mmus       = tl["mmu_id"].nunique()
missing_logout_n  = len(sessions_no_end)
missing_logout_pct = (missing_logout_n / total_sessions * 100) if total_sessions else 0
total_faults      = ps["fault_flag"].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Shift Sessions",   f"{total_sessions}")
k2.metric("Active MMUs",            f"{active_mmus}")
k3.metric("Missing Logouts",
          f"{missing_logout_n}",
          delta=f"{missing_logout_pct:.0f}% of sessions",
          delta_color="inverse")
k4.metric("Pre-start Faults Flagged", f"{int(total_faults)}")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_logout, tab_util, tab_prestart = st.tabs([
    "🔴  Missing Logouts",
    "📊  MMU Utilization",
    "⚠️  Pre-start Faults",
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — MISSING LOGOUTS
# ════════════════════════════════════════════════════════════════════════════════
with tab_logout:
    st.subheader("Operators who started a shift but did not log Shift End")
    st.markdown(
        "Each row below is a shift session with a **Shift Start** but no corresponding **Shift End**. "
        "This means the operator's activity cannot be accurately tracked after their last logged event, "
        "and utilization calculations are incomplete for these sessions."
    )

    col_a, col_b = st.columns([1, 1])

    with col_a:
        # Bar: missing logouts by operator
        by_op = (
            sessions_no_end.groupby("operator_name")
            .size()
            .reset_index(name="sessions_missing_logout")
            .sort_values("sessions_missing_logout", ascending=True)
        )
        fig_op = px.bar(
            by_op,
            x="sessions_missing_logout",
            y="operator_name",
            orientation="h",
            title="Missing Logouts by Operator",
            labels={"sessions_missing_logout": "Sessions without Shift End", "operator_name": "Operator"},
            color="sessions_missing_logout",
            color_continuous_scale=[[0, "#FFA726"], [1, "#E53935"]],
        )
        fig_op.update_layout(showlegend=False, coloraxis_showscale=False, height=400)
        st.plotly_chart(fig_op, use_container_width=True)

    with col_b:
        # Bar: missing logouts by date
        by_date = (
            sessions_no_end.groupby("reporting_date")
            .size()
            .reset_index(name="count")
            .sort_values("reporting_date")
        )
        fig_date = px.bar(
            by_date,
            x="reporting_date",
            y="count",
            title="Missing Logouts by Date",
            labels={"count": "Sessions without Shift End", "reporting_date": "Date"},
            color_discrete_sequence=[COLOURS["orange"]],
        )
        fig_date.update_layout(height=400)
        st.plotly_chart(fig_date, use_container_width=True)

    # Detail table
    st.markdown("#### Session detail")
    display_no_end = sessions_no_end[[
        "operator_name", "mmu_id", "reporting_date", "shift_start"
    ]].rename(columns={
        "operator_name": "Operator",
        "mmu_id":        "MMU",
        "reporting_date":"Date",
        "shift_start":   "Shift Start Time",
    }).sort_values(["Date", "MMU"])

    st.dataframe(
        display_no_end.reset_index(drop=True),
        use_container_width=True,
        height=300,
    )

    if not sessions_no_end.empty:
        csv_no_end = display_no_end.to_csv(index=False).encode()
        st.download_button("⬇ Download missing logouts CSV", csv_no_end,
                           "missing_logouts.csv", "text/csv")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — MMU UTILIZATION
# ════════════════════════════════════════════════════════════════════════════════
with tab_util:
    st.subheader("Time on task — by MMU and activity type")
    st.markdown(
        "Shows how time is distributed across operational activities for each truck. "
        "Durations are capped at 4 hours per activity to prevent unmatched sessions from distorting the chart."
    )

    col_c, col_d = st.columns([3, 2])

    with col_c:
        # Stacked bar: hours by MMU, stacked by activity type
        util = (
            activity_tl.groupby(["mmu_id", "activity_type"])["duration_hours"]
            .sum()
            .reset_index()
            .sort_values("mmu_id")
        )
        colour_map = {act: ACTIVITY_COLOURS.get(act, "#95A5A6") for act in util["activity_type"].unique()}
        fig_util = px.bar(
            util,
            x="mmu_id",
            y="duration_hours",
            color="activity_type",
            title="Total Activity Hours by MMU",
            labels={"mmu_id": "MMU", "duration_hours": "Hours", "activity_type": "Activity"},
            color_discrete_map=colour_map,
        )
        fig_util.update_layout(height=450, legend_title="Activity Type")
        st.plotly_chart(fig_util, use_container_width=True)

    with col_d:
        # Donut: overall time split by activity
        overall = (
            activity_tl.groupby("activity_type")["duration_hours"]
            .sum()
            .reset_index()
            .sort_values("duration_hours", ascending=False)
        )
        colour_list = [ACTIVITY_COLOURS.get(a, "#95A5A6") for a in overall["activity_type"]]
        fig_donut = px.pie(
            overall,
            names="activity_type",
            values="duration_hours",
            title="Activity Mix (all MMUs)",
            hole=0.45,
            color="activity_type",
            color_discrete_map=ACTIVITY_COLOURS,
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label")
        fig_donut.update_layout(height=450, showlegend=False)
        st.plotly_chart(fig_donut, use_container_width=True)

    # Daily utilization trend
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
            color_discrete_map=ACTIVITY_COLOURS,
        )
        fig_trend.update_layout(height=320, legend_title="Activity Type")
        st.plotly_chart(fig_trend, use_container_width=True)

    # Summary table
    st.markdown("#### Hours by MMU and activity")
    pivot = (
        activity_tl.groupby(["mmu_id", "activity_type"])["duration_hours"]
        .sum()
        .round(1)
        .unstack(fill_value=0)
        .reset_index()
    )
    pivot.columns.name = None
    st.dataframe(pivot, use_container_width=True, height=280)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — PRE-START FAULTS
# ════════════════════════════════════════════════════════════════════════════════
with tab_prestart:
    st.subheader("MMU Pre-Start Checklist — Fault Summary")
    st.markdown(
        "Checklist items flagged as faults during daily pre-start inspections. "
        "Items are classified into four categories: **IN CAB CHECKS**, **EXTERNAL CHECKS**, "
        "**QUALITY**, and **BEFORE DRIVING OFF**."
    )

    faults = ps[ps["fault_flag"]].copy()
    all_checks = ps.copy()

    col_e, col_f = st.columns([1, 1])

    with col_e:
        # Faults by MMU
        faults_by_mmu = (
            faults.groupby("mmu_id")
            .size()
            .reset_index(name="fault_count")
            .sort_values("fault_count", ascending=True)
        )
        fig_mmu_fault = px.bar(
            faults_by_mmu,
            x="fault_count",
            y="mmu_id",
            orientation="h",
            title="Fault Flags by MMU",
            labels={"fault_count": "Fault Flags", "mmu_id": "MMU"},
            color="fault_count",
            color_continuous_scale=[[0, "#FFA726"], [1, "#E53935"]],
        )
        fig_mmu_fault.update_layout(showlegend=False, coloraxis_showscale=False, height=380)
        st.plotly_chart(fig_mmu_fault, use_container_width=True)

    with col_f:
        # Faults by checklist category
        faults_by_cat = (
            faults.groupby("checklist_category")
            .size()
            .reset_index(name="fault_count")
            .sort_values("fault_count", ascending=False)
        )
        fig_cat = px.pie(
            faults_by_cat,
            names="checklist_category",
            values="fault_count",
            title="Faults by Checklist Category",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_cat.update_traces(textposition="outside", textinfo="percent+label")
        fig_cat.update_layout(height=380, showlegend=False)
        st.plotly_chart(fig_cat, use_container_width=True)

    # Heatmap: fault rate by item across all inspections
    st.markdown("#### Most frequently flagged checklist items")

    item_fault_rate = (
        all_checks.groupby(["checklist_category", "checklist_item"])
        .agg(
            total_checks=("fault_flag", "count"),
            fault_count=("fault_flag", "sum"),
        )
        .reset_index()
    )
    item_fault_rate["fault_rate_pct"] = (
        item_fault_rate["fault_count"] / item_fault_rate["total_checks"] * 100
    ).round(1)
    item_fault_rate = item_fault_rate[item_fault_rate["fault_count"] > 0].sort_values(
        "fault_count", ascending=False
    )

    # Truncate long item names for display
    item_fault_rate["item_short"] = item_fault_rate["checklist_item"].str[:60] + "…"

    fig_items = px.bar(
        item_fault_rate.head(15),
        x="fault_count",
        y="item_short",
        color="checklist_category",
        orientation="h",
        title="Top 15 Most Flagged Items",
        labels={"fault_count": "Fault Count", "item_short": "", "checklist_category": "Category"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_items.update_layout(height=420, legend_title="Category", yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_items, use_container_width=True)

    # Fault record detail
    st.markdown("#### Fault records (inspections with flagged items)")
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
        csv_faults = fault_detail.to_csv(index=False).encode()
        st.download_button("⬇ Download fault records CSV", csv_faults,
                           "prestart_faults.csv", "text/csv")


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "MMU Operations Dashboard · Kansanshi · Data sourced from Jotform exports via normalized pipeline. "
    "Durations capped at 240 min per activity. Missing Shift End sessions are flagged as exceptions."
)
