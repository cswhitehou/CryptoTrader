import requests
import backtrader as bt
import backtrader.analyzers as btanalyzers
import json
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt


def get_binance_bars(symbol, interval, startTime, endTime):
    url = "https://api.binance.com/api/v3/klines"

    startTime = str(int(startTime.timestamp() * 1000))
    endTime = str(int(endTime.timestamp() * 1000))
    limit = '1000'

    req_params = {"symbol": symbol, 'interval': interval, 'startTime': startTime, 'endTime': endTime, 'limit': limit}

    df = pd.DataFrame(json.loads(requests.get(url, params=req_params).text))

    if (len(df.index) == 0):
        return None

    df = df.iloc[:, 0:6]
    df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']

    df.open = df.open.astype("float")
    df.high = df.high.astype("float")
    df.low = df.low.astype("float")
    df.close = df.close.astype("float")
    df.volume = df.volume.astype("float")

    df['adj_close'] = df['close']

    df.index = [dt.datetime.fromtimestamp(x / 1000.0) for x in df.datetime]

    return df

count = 0
df_list = []
last_datetime = dt.datetime(2023, 1, 1)
while True:
    new_df = get_binance_bars('LINKUSDT', '1h', last_datetime, dt.datetime.now())
    if new_df is None:
        break
    df_list.append(new_df)
    last_datetime = max(new_df.index) + dt.timedelta(0, 1)
    count+=1
    if count >= 165:
        break


df = pd.concat(df_list)
df.shape
csv_file_path = "link_usd_1hr_data.csv"
df.to_csv(csv_file_path)
print(df)
