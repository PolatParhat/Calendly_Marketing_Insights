"""Dashboard maths on top of the Gold tables (pandas only, no Streamlit, so it is easy to test).

Gold holds counts and sums per day or week. Everything here adds them up over the period the user
picks, so CPB (Cost Per Booking) is always total spend / total bookings, never an average of daily CPBs.
"""

from datetime import date, timedelta

import pandas as pd

CHANNELS = ["facebook_paid_ads", "youtube_paid_ads", "tiktok_paid_ads"]
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]  # as Silver writes them (EEEE)


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def weeks_in_period(start: date, end: date) -> int:
    """Number of Monday-Sunday weeks the period touches (metric 1.6 divides by this)."""
    return (monday(end) - monday(start)).days // 7 + 1


def filter_days(df: pd.DataFrame, column: str, start: date, end: date, channels: list[str]):
    out = df[(df[column] >= start) & (df[column] <= end)]
    return out[out["channel"].isin(channels)] if "channel" in out else out


def total_spend(daily_spend_bookings: pd.DataFrame) -> float | None:
    """Sum of known spend; None when no spend is known yet (e.g. today: published tomorrow 06:00)."""
    spend = daily_spend_bookings["spend_usd"].astype(float).sum(min_count=1)
    return None if pd.isna(spend) else float(spend)


def cpb_note(spend: float | None, bookings: int) -> str | None:
    """Why there is no CPB number: unknown spend is not free spend, and 0 bookings can't divide."""
    if spend is None or pd.isna(spend):
        return "spend not published yet"
    if not bookings:
        return "no bookings"
    return None


def cpb_by_channel(daily_spend_bookings: pd.DataFrame) -> pd.DataFrame:
    """1.2: per channel: total spend, total bookings, CPB; `note` says why CPB is missing."""
    sums = daily_spend_bookings.groupby("channel", as_index=False).agg(
        spend_usd=("spend_usd", lambda s: s.astype(float).sum(min_count=1)),
        bookings=("bookings", "sum"),
    )
    sums["bookings"] = sums["bookings"].astype(int)
    sums["note"] = [cpb_note(s, b) for s, b in zip(sums["spend_usd"], sums["bookings"])]
    sums["cpb_usd"] = [
        None if note else round(s / b, 2)
        for s, b, note in zip(sums["spend_usd"], sums["bookings"], sums["note"])
    ]
    return sums.sort_values("cpb_usd", na_position="last").reset_index(drop=True)


def overall_cpb(daily_spend_bookings: pd.DataFrame) -> float | None:
    spend = total_spend(daily_spend_bookings)
    bookings = int(daily_spend_bookings["bookings"].sum())
    return None if cpb_note(spend, bookings) else round(spend / bookings, 3)


def daily_with_cumulative(daily_bookings: pd.DataFrame) -> pd.DataFrame:
    """1.1 + 1.3: bookings per day and channel, running total within the selected period."""
    out = daily_bookings.sort_values("booking_date")[["booking_date", "channel", "bookings"]].copy()
    out["cumulative_bookings"] = out.groupby("channel")["bookings"].cumsum()
    return out.reset_index(drop=True)


def campaign_leaderboard(by_campaign: pd.DataFrame) -> pd.DataFrame:
    """1.4: bookings per channel and campaign, best first."""
    return (
        by_campaign.groupby(["channel", "campaign"], as_index=False)["bookings"]
        .sum()
        .sort_values(["bookings", "channel", "campaign"], ascending=[False, True, True])
        .reset_index(drop=True)
    )


def time_slot_grid(by_time_slot: pd.DataFrame) -> pd.DataFrame:
    """1.5: bookings per weekday (rows, Mon first) and hour (columns, US Eastern)."""
    grid = by_time_slot.pivot_table(
        index="meeting_day_of_week",
        columns="meeting_hour_et",
        values="bookings",
        aggfunc="sum",
        fill_value=0,
    )
    return grid.reindex([d for d in DAY_ORDER if d in grid.index])


def meeting_load(weekly_by_host: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """1.6: average marketing meetings per week per host = total meetings / weeks in the period."""
    weeks = weeks_in_period(start, end)
    in_period = weekly_by_host[
        (weekly_by_host["week_start"] >= monday(start)) & (weekly_by_host["week_start"] <= end)
    ]
    out = in_period.groupby(["host_user_id", "host_name"], as_index=False)["meetings"].sum()
    out["weeks"] = weeks
    out["avg_meetings_per_week"] = (out["meetings"] / weeks).round(2)
    return out.sort_values("avg_meetings_per_week", ascending=False).reset_index(drop=True)
