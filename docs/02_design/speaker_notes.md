# Speaker notes: design review with the SME

**How to use this:** read the **Say** parts out loud. **Show** tells you what to put on screen.
Each part ends with a **Next** line that leads you into the following part.
Total: about 12 minutes, then questions.

---

## Part 1. Opening (1 min)

**Show:** nothing yet.

**Say:**

"Thanks for making time today.

Marketing runs ads on Facebook, YouTube and TikTok. People click an ad and book a call in Calendly.

This project answers one simple question: **which channel gets us booked calls for the least money?**

To answer it, I bring together two things: every booking, and the daily ad spend.

I'll show you how the data flows, how it's stored, and how I keep it safe and reliable.
At the end, I'll ask for your approval to start building."

**Next:** "Let's start with the big picture."

---

## Part 2. The big picture: follow one booking (4 min)

**Show:** architecture.png

**Say:**

"This diagram has the same five sections as the one in the requirements.
The easiest way to read it is to follow one booking from left to right."

*(point at Calendly)*
"**One:** someone books a call. Calendly instantly sends us a message about it. That's the webhook."

*(point at API Gateway and the Lambda)*
"**Two:** the message arrives at our web address. A small function checks that it really came from Calendly,
then saves it in S3, exactly as it arrived."

*(point at EMR and the Bronze, Silver, Gold boxes)*
"**Three:** once a day, a Spark job cleans the data and stores it in three layers: Bronze, Silver and Gold.
I'll explain those in a minute."

*(point at Athena)*
"**Four:** Athena lets us query the final tables with plain SQL."

*(point at Streamlit)*
"**Five:** the dashboard shows the six metrics."

*(point at Marketing spend, bottom left)*
"The ad spend takes a shorter route. Every morning, a second small function copies the spend files into our S3.
The same daily job picks them up from there."

**Next:** "That's how the data gets in. Now, the three things the requirements ask for: scheduling, failure handling and encryption. They're in the bottom band."

---

## Part 3. Scheduling, safety nets, security (3 min)

**Show:** architecture.png, bottom band.

*(point at Scheduling)*
**Say:**

"The spend files arrive at 6 AM Eastern.
At **7 AM**, a scheduler starts the daily run. The extra hour is a safety margin."

*(point at Failure reload)*
"If something breaks, there are three safety nets.

**First,** every step retries automatically. If it still fails, I get an email.

**Second,** if a booking can't be saved, it waits in a queue and gets saved on the next run. Nothing is lost.

**Third,** every run *updates* rows instead of adding new ones.
So I can always re-run safely. Nothing gets counted twice."

*(point at Security)*
"All data is encrypted, both when stored and when moving.
Each service can only touch what it needs.
Personal details, like names and emails, never reach the dashboard. It only shows totals."

*(point at CI/CD)*
"And everything is written as code and tested automatically on GitHub before any change goes live."

**Next:** "Now let's look at how the data is organised."

---

## Part 4. The data model (3 min)

**Show:** data_model.png

**Say:**

"Again, read it left to right."

*(point at Bronze)*
"**Bronze** is the raw data, exactly as it arrived. It's our backup. If anything goes wrong, we rebuild from here."

*(point at Silver)*
"**Silver** is the clean version. We keep only the three marketing channels,
turn the raw message into proper columns, and remove duplicates.

This is where your rules live: the booking date, Eastern time, the campaign, and the meeting hour."

*(point at booking_hosts)*
"One detail: a meeting can have more than one host, so hosts get their own small table.
That's what the meeting-load metric counts."

*(point at Gold)*
"**Gold** has one small table per metric, ready for the dashboard."

"One important point about **cost per booking**.
I always divide total spend by total bookings for the period you choose. I never average daily numbers.

A quick example:
- Day 1: $100 spent, 10 bookings. That's $10 per booking.
- Day 2: $100 spent, 1 booking. That's $100 per booking.
- Averaging the two days gives $55. That's wrong.
- The real cost is $200 for 11 bookings: about **$18** per booking."

**Next:** "Two small questions are still open."

---

## Part 5. Open questions and approval (1 min)

**Show:** nothing, or the end of solution_design.md.

**Say:**

"**First, meeting load.** I count only meetings from the three marketing channels.
Should a meeting count in the week it *happens*, or the week it was *booked*?
I suggest the week it happens."

"**Second, the campaign heatmap.** Spend only comes per channel, not per campaign.
So I suggest the heatmap shows *bookings* per campaign, and cost per booking stays per channel."

*(write their answers down)*

"If you're happy with the design, could you confirm your approval by email?
Then I'll start building. The first thing you'll get from me is the webhook URL."

---

## If they ask...

Short answers first. Add the second sentence only if they want more.

**"Why not Databricks?"**
The requirements say everything must be on AWS, and Databricks is a separate company.
EMR Serverless runs the same Spark, and costs nothing when it's not running.

**"Why not Redshift?"**
You confirmed Athena. It reads the tables where they are, with no copying, and we only pay when we query.

**"How up to date is the dashboard?"**
It shows everything up to yesterday, updated every morning at 7.
That matches the spend data, which is also one day behind.

**"What if Calendly sends the same booking twice?"**
Each booking has a unique ID. A repeat just updates the same row, so it's never counted twice.

**"What if your system is down when someone books?"**
If saving fails, the booking waits in a queue and is saved the next morning.
If the whole system is down, I get an alert straight away.

**"What if a spend number gets corrected later?"**
Every day I re-read all the spend files. The newest number always wins.

**"How do you know the numbers are right?"**
Automatic tests compare the results with numbers I calculated by hand.
And I'll make test bookings on all three channels to check the whole flow.

**"How is personal data protected?"**
It's encrypted, only a few services can read it, and the dashboard only shows totals.

**"What does it cost?"**
Very little. Nothing runs when it's idle, and the daily job takes only a few minutes.

**"What if we add a fourth channel?"**
I add one line to a settings list and redeploy. No tables change.

---

## If you lose your place

The whole design in five lines:
1. Calendly sends each booking to us instantly. We check it and save it.
2. Every morning we copy the ad spend files.
3. At 7 AM a Spark job cleans everything into Bronze, Silver and Gold.
4. Athena queries Gold; the dashboard shows the six metrics.
5. Retries, a queue, safe re-runs and encryption keep it reliable and secure.
