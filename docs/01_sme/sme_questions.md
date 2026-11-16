# SME questions (drafted 2026-11-16)

Status: sent; answered 2026-11-16 (see Answers). Originally: drafted; user to send. Record the SME's answers under "Answers" below when they arrive,
then update the working assumptions in docs/decisions.md.

---

**Subject: Calendly Marketing Insights: questions before architecture approval**

Hi,

I'm starting the Calendly Marketing Insights project and have read the requirements document. Before I present the architecture and data model for approval, I'd like to confirm a few points. For each question I've included the assumption I'll work with unless you tell me otherwise, so a quick "OK" or a correction is all I need.

**Webhook setup**
- When I send you my endpoint URL and you create the `invitee.created` webhook, could you also share the webhook's signing key? My endpoint would use it to verify that incoming requests really come from Calendly.
  *Assumption: yes. I'll store the key securely in AWS Secrets Manager.*
- May I make a few test bookings on the Facebook, YouTube and TikTok booking pages to check the pipeline end to end?

**Booking date and time zone**
- Should a booking be dated by when the lead made the booking (`created_at`), or by when the meeting takes place (`start_time`)?
  *Assumption: when the lead made the booking. This date is used for "Daily Calls Booked by Source", "Cost Per Booking by Channel" and "Bookings Trend Over Time".*
- Which time zone should define a "day" and an "hour" on the dashboard? Webhook timestamps are in UTC (Coordinated Universal Time), and the spend files arrive at 06:00 AM EST.
  *Assumption: US Eastern time.*

**Channel and campaign attribution**
- In the sample webhook, the UTM (Urchin Tracking Module) fields are all null, and the spend file only has a `channel` column. Where should "campaign" come from for the "CPB by Channel and Campaign" heatmap?
  *Assumption: source = the channel identified by the three event types. Campaign = `utm_campaign` when present, otherwise "unknown".*

**Booking Volume by Time Slot / Day of Week**
- Does "time slot" mean the moment the lead booked, or the meeting slot they chose?
  *Assumption: the moment the lead booked.*

**Meeting Load per Employee**
- Should this count only meetings from the three marketing event types, or all meetings in the organization that the webhook delivers?
  *Assumption: all meetings, since the goal is to measure each employee's total workload.*

**Cancellations**
- The requirements mention only `invitee.created`. Should bookings that are later cancelled still be counted?
  *Assumption: yes, all bookings are counted.*

**Historical data**
- The webhook only sends bookings made after it's created. Do you need bookings from before that date (a backfill)? If so, could I get a Calendly API token?
  *Assumption: no backfill. The data starts when the webhook goes live.*

**Data warehouse**
- Is Amazon Athena, querying the Gold Delta Lake tables on S3, acceptable for the "Data Warehouse" part of the architecture, or do you expect Amazon Redshift?
  *Assumption: Athena.*

Thank you! I'll send the architecture diagram, data model and my endpoint URL once these are confirmed.

Best regards,
Polat

---

## Answers
Received 2026-11-16. SME reply (verbatim):

> Please share your webhook URL and we can provide the signing key. You can make test bookings for all three channels.
> Use created_at for booking metrics, US Eastern time for reporting, and the event type to identify the channel.
> For campaigns use utm_campaign when available otherwise use Unknown. For booking time slots use the meeting start_time.
> Cancellation tracking and historical backfill are not required. Athena is fine for querying Gold Delta tables on S3.

| # | Question | Answer | vs. our assumption |
|---|----------|--------|--------------------|
| 1 | Signing key | Yes, after we send the webhook URL | same |
| 2 | Test bookings | Yes, on all three channels | same |
| 3 | Booking date | `created_at` | same |
| 4 | Time zone | US Eastern | same |
| 5 | Channel / campaign | Channel = event type; campaign = `utm_campaign`, else "Unknown" | same (spelling: "Unknown") |
| 6 | Time slot (metric 1.5) | Meeting `start_time` | **changed** (we assumed booking moment) |
| 7 | Meeting-load scope (metric 1.6) | _not answered_; user decided 2026-11-16: 3 marketing channels only | **changed** (we assumed all meetings) |
| 8 | Cancellations | Not required | same (`invitee.created` only) |
| 9 | Historical backfill | Not required | same |
| 10 | Data warehouse | Athena over Gold Delta tables is fine | same |


---

# Follow-up questions (drafted 2026-11-16)

Status: sent; answered 2026-11-16 (see "Follow-up answers").

---

**Subject: Calendly Marketing Insights: two follow-up questions**

Hi,

Thank you for the quick answers, they settled almost everything. While designing the data model, two
points came up where I'd like your confirmation. As before, I've included what I plan to do, so an "OK"
or a correction is all I need.

**1. Meeting Load per Employee: which week does a meeting count in?**
The formula is Avg Meetings per Week = Total Meetings / Number of Weeks. A meeting can be booked in one
week and held in the next. Should it count in the week it was **booked** (`created_at`) or the week it
**takes place** (`start_time`)?
*Plan: the week it takes place, since the metric measures the meetings employees actually attend.*

For your information: I'll count only meetings from the three marketing event types (Facebook, YouTube,
TikTok), so the metric shows the load created by paid marketing. Please let me know if you'd rather
include all meetings in the organization.

**2. "CPB by Channel and Campaign" heatmap**
The spend files give spend per **channel** only, with no campaign column, so the true cost per booking
can't be calculated for each campaign. Which would you prefer?
- **a)** The heatmap shows **number of bookings** by channel × campaign, and CPB is shown per channel only.
- **b)** Each channel's spend is split across its campaigns in proportion to their bookings, giving an
  **estimated** CPB per campaign (clearly labelled as an estimate).

*Plan: option a), because every number on it is exact.*

Once these are confirmed, I'll send the architecture diagram, data model and solution design for your
written approval.

Best regards,
Polat

---

## Follow-up answers
Received 2026-11-16. SME reply (verbatim):

> yes you can use start_time to calculate Meeting Load per Employee by week and include only the three marketing event types.
> For CPB go with option A since the spend data is available only at the channel level. You can show bookings by channel
> and campaign, and calculate CPB separately at the channel level. This approach is fine.

| # | Question | Answer | vs. our plan |
|---|----------|--------|--------------|
| 1 | Meeting load (1.6): which week, and which meetings | Week of the meeting `start_time`; only the 3 marketing event types | same |
| 2 | "CPB by Channel and Campaign" heatmap | Option a): heatmap shows bookings by channel × campaign; CPB at channel level only | same |
