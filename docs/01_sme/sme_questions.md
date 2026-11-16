# SME questions (drafted 2026-11-16)

Status: drafted; user to send. Record the SME's answers under "Answers" below when they arrive,
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
_(none yet)_
