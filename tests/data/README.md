# Test data: sample landing files and the hand-calculated answers

Small, fake files shaped exactly like the real ones (webhook JSON from the requirements' sample,
spend JSON from the public bucket). No real personal data: names are "Test Lead N", emails `@example.com`.
The tests run the pipeline on these files and compare the results with the answers below.

All dates in November 2026 are after daylight-saving ended (1 Nov), so **US Eastern = UTC − 5 hours**.

## Webhook files (`landing/calendly/dt=<day received>/<invitee id>.json`)

| File | Booking | Event type | Booked (UTC) | Booked (ET) | Meeting start (ET) | Hosts | utm_campaign | What it tests |
|---|---|---|---|---|---|---|---|---|
| dt=2026-11-02/…01 | 1 | Facebook | 11-02 14:30 | **Mon 11-02** 09:30 | Wed 11-04 10:00 | Alice | fall_promo | normal booking |
| dt=2026-11-03/…01 | 1 again | Facebook | 11-02 14:30 | Mon 11-02 09:30 | Wed 11-04 10:00 | Alice | fall_promo | **duplicate delivery**: must collapse to 1 row |
| dt=2026-11-03/…02 | 2 | Facebook | **11-03** 03:30 | **Mon 11-02** 22:30 | Thu 11-05 14:00 | Bob | null | **UTC date ≠ ET date**; null campaign → "Unknown" |
| dt=2026-11-03/…03 | 3 | YouTube | 11-03 16:00 | Tue 11-03 11:00 | Tue 11-10 09:00 | Alice | yt_webinar | meeting in the **next week** |
| dt=2026-11-03/…06 | 6 | Info Session | 11-03 10:00 | Tue 11-03 05:00 | Sat 11-07 10:00 | Bob | null | **not marketing**: stays in Bronze, dropped in Silver |
| dt=2026-11-04/…04 | 4 | TikTok | 11-04 20:15 | Wed 11-04 15:15 | Fri 11-06 16:00 | Alice + Bob | "" (empty) | **two hosts**; empty campaign → "Unknown" |

## Spend files (`landing/spend/dt=<day received>/spend_data_<Day-1>.json`)

| File | Covers | Note |
|---|---|---|
| spend_data_2026-11-02.json | 11-01, 11-02 | facebook 11-02 = 120.00 |
| spend_data_2026-11-03.json | 11-01, 11-02, 11-03 | overlaps the first file; **facebook 11-02 restated to 125.50** |

| Date | facebook_paid_ads | youtube_paid_ads | tiktok_paid_ads |
|---|---|---|---|
| 11-01 | 100.00 | 80.00 | 50.00 |
| 11-02 | 125.50 (newest file wins) | 90.00 | 60.00 |
| 11-03 | 110.00 | 70.00 | 40.00 |

## Expected results

**Bronze**
- calendly_events_raw: **6** rows (every file, including the duplicate and the non-marketing one).
- spend_raw: **15** rows (6 + 9).

**Silver**
- bookings: **4** rows (bookings 1, 2, 3, 4).
- booking_hosts: **5** rows (1 Alice, 2 Bob, 3 Alice, 4 Alice, 4 Bob).
- spend_daily: **9** rows (3 days × 3 channels); facebook 11-02 = **125.50**.

**Gold**

1.1 Daily bookings by channel (booking date, ET)

| booking_date | channel | bookings |
|---|---|---|
| 2026-11-02 | facebook_paid_ads | 2 |
| 2026-11-03 | youtube_paid_ads | 1 |
| 2026-11-04 | tiktok_paid_ads | 1 |

1.2 CPB (Cost Per Booking) over the whole period = total spend ÷ total bookings

| channel | spend | bookings | CPB |
|---|---|---|---|
| facebook_paid_ads | 335.50 | 2 | 167.75 |
| youtube_paid_ads | 240.00 | 1 | 240.00 |
| tiktok_paid_ads | 150.00 | 1 | 150.00 |
| **all** | **725.50** | **4** | **181.375** |

(TikTok on 11-04 has 1 booking and no spend row yet: it appears with spend 0/null, not dropped.)

1.3 Weekly bookings (week starts Monday 2026-11-02): facebook 2, youtube 1, tiktok 1.

1.4 Bookings by campaign: facebook / fall_promo 1 · facebook / Unknown 1 · youtube / yt_webinar 1 · tiktok / Unknown 1.

1.5 Bookings by meeting slot (ET): facebook Wed 10:00 · facebook Thu 14:00 · youtube Tue 09:00 · tiktok Fri 16:00 (1 each).

1.6 Meetings per host per week (week of meeting start, Monday):

| week_start | host | meetings |
|---|---|---|
| 2026-11-02 | Alice Host | 2 (bookings 1, 4) |
| 2026-11-02 | Bob Host | 2 (bookings 2, 4) |
| 2026-11-09 | Alice Host | 1 (booking 3) |
