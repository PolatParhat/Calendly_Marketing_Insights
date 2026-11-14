# Calendly Marketing Insights

An AWS data pipeline that combines Calendly bookings (received by webhook) with daily marketing
spend, stores them in Delta Lake on S3, and shows marketing and meeting metrics in a Streamlit
dashboard. The main metric is Cost Per Booking by channel.

## Docs
- [Requirements](docs/00_requirements/requirements.txt) ([original PDF](docs/00_requirements/Calendly_Marketing_Insights.docx.pdf))
- Architecture options: [A: Delta Lake + EMR](docs/00_requirements/architecture_option_A_emr_delta_lake.jpg) ·
  [B: Databricks](docs/00_requirements/architecture_option_B_databricks.jpg)
- [Decisions and change log](docs/decisions.md)
- [Current status](STATUS.md)

## Steps
_Filled in as the project grows._
