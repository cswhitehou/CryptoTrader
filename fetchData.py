import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Calculate the start date for the past two months
end_date = datetime.now()
start_date = end_date - timedelta(days=59)  # approximately 2 months

# Fetch the data
df = yf.Ticker("APT-USD").history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), interval="5m")
csv_file_path = "data/apt_yf_5min_data.csv"
df.to_csv(csv_file_path)

print(df)
