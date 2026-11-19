"""Calendly Marketing Insights dashboard: the six metrics (1.1-1.6) from the Gold tables.

Run against AWS (Athena):
    streamlit run dashboard/app.py
Run against a local lake folder (no AWS), e.g. after `python -m calendly_insights.pipeline`:
    DASHBOARD_SOURCE=local LAKE_PATH=lake streamlit run dashboard/app.py

Settings (environment variables): DASHBOARD_SOURCE (athena|local), LAKE_PATH,
ATHENA_DATABASE (calendly_gold), ATHENA_WORKGROUP (calendly-insights), AWS_REGION.
"""

import os
from datetime import date

import altair as alt
import data_source
import metrics
import pandas as pd
import streamlit as st

# Fixed colour per channel (validated categorical palette); a filter never repaints a channel.
CHANNEL_COLORS = {
    "facebook_paid_ads": "#2a78d6",
    "youtube_paid_ads": "#eb6834",
    "tiktok_paid_ads": "#1baf7a",
}
CHANNEL_SCALE = alt.Scale(domain=list(CHANNEL_COLORS), range=list(CHANNEL_COLORS.values()))
SEQUENTIAL = alt.Scale(range=["#cde2fb", "#104281"])  # one hue, light -> dark = few -> many

SOURCE = os.getenv("DASHBOARD_SOURCE", "athena")

st.set_page_config(page_title="Calendly Marketing Insights", layout="wide")


@st.cache_data(ttl=600, show_spinner="Loading Gold tables...")
def load(table: str) -> pd.DataFrame:
    if SOURCE == "local":
        return data_source.read_local(table, os.getenv("LAKE_PATH", "lake"))
    return data_source.read_athena(
        table,
        database=os.getenv("ATHENA_DATABASE", "calendly_gold"),
        workgroup=os.getenv("ATHENA_WORKGROUP", "calendly-insights"),
        region=os.getenv("AWS_REGION"),
    )


def table_view(df: pd.DataFrame, label: str = "Show data table") -> None:
    with st.expander(label):
        st.dataframe(df, hide_index=True, width="stretch")


gold = {name: load(name) for name in data_source.GOLD_TABLES}
daily = gold["daily_bookings_by_channel"]
if daily.empty:
    st.warning("No bookings in Gold yet. Run the pipeline first.")
    st.stop()

# ---------------------------------------------------------------- header and filters (one row)
st.title("Calendly Marketing Insights")
st.caption(f"Booked calls and ad spend by channel · data source: {SOURCE} · times in US Eastern")

first_day = min(daily["booking_date"].min(), gold["daily_spend_bookings_by_channel"]["date"].min())
last_day = max(daily["booking_date"].max(), gold["daily_spend_bookings_by_channel"]["date"].max())
col_dates, col_channels = st.columns([1, 2])
picked = col_dates.date_input(
    "Period", value=(first_day, last_day), min_value=first_day, max_value=last_day
)
start, end = (picked[0], picked[1]) if len(picked) == 2 else (picked[0], picked[0])
channels = col_channels.multiselect("Channels", metrics.CHANNELS, default=metrics.CHANNELS)
if not channels:
    st.info("Pick at least one channel.")
    st.stop()

day_bookings = metrics.filter_days(daily, "booking_date", start, end, channels)
day_spend = metrics.filter_days(gold["daily_spend_bookings_by_channel"], "date", start, end, channels)

# ---------------------------------------------------------------- headline numbers
total_bookings = int(day_bookings["bookings"].sum())
total_spend = float(day_spend["spend_usd"].sum())
cpb_all = metrics.overall_cpb(day_spend)
k1, k2, k3 = st.columns(3)
k1.metric("Booked calls", f"{total_bookings:,}")
k2.metric("Ad spend", f"${total_spend:,.2f}")
k3.metric("Average CPB (total spend ÷ total bookings)", f"${cpb_all:,.2f}" if cpb_all else "no bookings")

# ---------------------------------------------------------------- 1.1 and 1.2
left, right = st.columns(2)
with left:
    st.subheader("1.1 Daily calls booked by source")
    trend = metrics.daily_with_cumulative(day_bookings)
    st.altair_chart(
        alt.Chart(trend)
        .mark_line(point=alt.OverlayMarkDef(size=80), strokeWidth=2)
        .encode(
            x=alt.X("booking_date:T", title="Booking day"),
            y=alt.Y("bookings:Q", title="Calls booked"),
            color=alt.Color("channel:N", scale=CHANNEL_SCALE, title="Channel"),
            tooltip=["booking_date:T", "channel:N", "bookings:Q"],
        ),
        width="stretch",
    )
    table_view(trend)

with right:
    st.subheader("1.2 Cost per booking (CPB) by channel")
    cpb = metrics.cpb_by_channel(day_spend)
    bars = (
        alt.Chart(cpb.dropna(subset=["cpb_usd"]))
        .mark_bar(cornerRadiusEnd=4, height=24)
        .encode(
            y=alt.Y("channel:N", title=None, sort="x"),
            x=alt.X("cpb_usd:Q", title="CPB (USD)"),
            color=alt.Color("channel:N", scale=CHANNEL_SCALE, legend=None),
            tooltip=["channel:N", "spend_usd:Q", "bookings:Q", "cpb_usd:Q"],
        )
    )
    labels = bars.mark_text(align="left", dx=4, color="#52514e").encode(
        text=alt.Text("cpb_usd:Q", format="$,.2f")
    )
    st.altair_chart(bars + labels, width="stretch")
    st.caption("Lower is better. A channel with spend but no bookings shows 'no bookings'.")
    shown = cpb.assign(cpb_usd=cpb["cpb_usd"].map(lambda v: "no bookings" if pd.isna(v) else v))
    table_view(shown)

# ---------------------------------------------------------------- 1.3
st.subheader("1.3 Bookings trend")
left, right = st.columns(2)
with left:
    st.markdown("**Cumulative calls booked in the period**")
    st.altair_chart(
        alt.Chart(trend)
        .mark_line(strokeWidth=2, interpolate="step-after")
        .encode(
            x=alt.X("booking_date:T", title="Booking day"),
            y=alt.Y("cumulative_bookings:Q", title="Cumulative calls"),
            color=alt.Color("channel:N", scale=CHANNEL_SCALE, title="Channel"),
            tooltip=["booking_date:T", "channel:N", "cumulative_bookings:Q"],
        ),
        width="stretch",
    )
with right:
    st.markdown("**Weekly calls booked (weeks start Monday)**")
    weekly = gold["weekly_bookings_by_channel"]
    weekly = weekly[
        (weekly["week_start"] >= metrics.monday(start))
        & (weekly["week_start"] <= end)
        & weekly["channel"].isin(channels)
    ].assign(week=lambda d: d["is_partial_week"].map({True: "partial week", False: "full week"}))
    st.altair_chart(
        alt.Chart(weekly)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("week_start:T", title="Week starting", timeUnit="yearmonthdate"),
            y=alt.Y("sum(bookings):Q", title="Calls booked"),
            color=alt.Color("channel:N", scale=CHANNEL_SCALE, title="Channel"),
            opacity=alt.Opacity(
                "week:N", scale=alt.Scale(domain=["full week", "partial week"], range=[1, 0.45])
            ),
            tooltip=["week_start:T", "channel:N", "bookings:Q", "week:N"],
        ),
        width="stretch",
    )
    st.caption("Faded bars are partial weeks at the edges of the data, not real dips.")
table_view(weekly, "Show weekly data table")

# ---------------------------------------------------------------- 1.4
st.subheader("1.4 Channel attribution leaderboard (UTM campaign)")
by_campaign = metrics.filter_days(gold["bookings_by_campaign"], "booking_date", start, end, channels)
board = metrics.campaign_leaderboard(by_campaign)
left, right = st.columns([3, 2])
with left:
    st.altair_chart(
        alt.Chart(board)
        .mark_rect(stroke="#fcfcfb", strokeWidth=2)
        .encode(
            x=alt.X("campaign:N", title="Campaign (utm_campaign)"),
            y=alt.Y("channel:N", title=None),
            color=alt.Color("bookings:Q", scale=SEQUENTIAL, title="Calls booked"),
            tooltip=["channel:N", "campaign:N", "bookings:Q"],
        ),
        width="stretch",
    )
with right:
    board_cpb = board.merge(cpb[["channel", "cpb_usd"]], on="channel", how="left")
    st.dataframe(
        board_cpb.rename(columns={"cpb_usd": "channel CPB (USD)"}),
        hide_index=True,
        width="stretch",
    )
    st.caption("Spend exists per channel only, so CPB is shown per channel, not per campaign.")

# ---------------------------------------------------------------- 1.5
st.subheader("1.5 Booking volume by meeting time slot (US Eastern)")
slots = gold["bookings_by_time_slot"]
slots = slots[slots["channel"].isin(channels)]
grid = (
    slots.groupby(["meeting_day_of_week", "meeting_hour_et"], as_index=False)["bookings"].sum()
)
st.altair_chart(
    alt.Chart(grid)
    .mark_rect(stroke="#fcfcfb", strokeWidth=2)
    .encode(
        x=alt.X("meeting_hour_et:O", title="Hour of day (meeting start)"),
        y=alt.Y("meeting_day_of_week:N", title=None, sort=metrics.DAY_ORDER),
        color=alt.Color("bookings:Q", scale=SEQUENTIAL, title="Meetings"),
        tooltip=["meeting_day_of_week:N", "meeting_hour_et:O", "bookings:Q"],
    ),
    width="stretch",
)
st.caption("All bookings to date for the selected channels (this Gold table has no date column).")
table_view(metrics.time_slot_grid(slots).reset_index())

# ---------------------------------------------------------------- 1.6
st.subheader("1.6 Meeting load: average marketing meetings per week per employee")
load_df = metrics.meeting_load(gold["weekly_meetings_by_host"], start, end)
st.altair_chart(
    alt.Chart(load_df)
    .mark_bar(cornerRadiusEnd=4, height=20, color="#2a78d6")
    .encode(
        y=alt.Y("host_name:N", title=None, sort="-x"),
        x=alt.X("avg_meetings_per_week:Q", title="Meetings per week"),
        tooltip=["host_name:N", "meetings:Q", "weeks:Q", "avg_meetings_per_week:Q"],
    ),
    width="stretch",
)
st.caption(
    f"Total meetings ÷ {metrics.weeks_in_period(start, end)} week(s) in the period "
    f"({start:%Y-%m-%d} to {end:%Y-%m-%d}); all 3 marketing channels."
)
table_view(load_df[["host_name", "meetings", "weeks", "avg_meetings_per_week"]])

st.caption(f"Rendered {date.today():%Y-%m-%d}. Gold has no personal data (no invitee names, emails or phones).")
