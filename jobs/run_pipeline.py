"""EMR Serverless entry point (the script EMR runs; our package comes in calendly_insights.zip).

Step Functions starts it with:
  --landing s3://<lake bucket>/landing --lake s3://<lake bucket> --cloud
"""

from calendly_insights.pipeline import main

if __name__ == "__main__":
    main()
