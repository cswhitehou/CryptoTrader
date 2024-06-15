import pandas as pd
import backtrader as bt

df = pd.read_csv("data/1h_test_data.csv", parse_dates=['datetime'])

# Ensure the 'datetime' column is correctly parsed
df['datetime'] = pd.to_datetime(df['datetime'])

# Drop unnecessary columns
df.drop(columns=['adj_close'], inplace=True)

# Add the 'openinterest' column, setting it to 0
df['openinterest'] = 0

# Set the 'datetime' column as the index
df.set_index('datetime', inplace=True)

print(df)


data_feed = bt.feeds.PandasData(dataname=df)

# Create a Cerebro engine
cerebro = bt.Cerebro()

# Add the data feed to Cerebro
cerebro.adddata(data_feed)

cerebro.run()
