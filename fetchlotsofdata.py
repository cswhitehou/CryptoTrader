import requests
import backtrader as bt
import backtrader.analyzers as btanalyzers
import time
import json
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt


def get_binance_bars(symbol, interval, startTime, endTime):
    url = "https://api.binance.com/api/v3/klines"

    startTime = str(int(startTime.timestamp() * 1000))
    print(startTime)
    endTime = str(int(endTime.timestamp() * 1000))
    print(endTime)
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
last_datetime = dt.datetime(2024, 7, 1)
end_date = dt.datetime(2024, 7, 29)
while True:
    new_df = get_binance_bars('MATICUSDT', '1m', last_datetime, end_date)
    print(new_df)
    print(max(new_df.index))
    if new_df is None:
        break
    df_list.append(new_df)
    last_datetime = max(new_df.index) + dt.timedelta(0, 1)
    print(last_datetime)
    count+=1
    time.sleep(0.5)
    if count >= 68:
        break


df = pd.concat(df_list)
df.shape
csv_file_path = "data_1min/matic_usd_1min_data6.csv"
df.to_csv(csv_file_path)
print(df)
count = 0
df_list = []
last_datetime = dt.datetime(2024, 7, 1)
end_date = dt.datetime(2024, 7, 29)
while True:
    new_df = get_binance_bars('DOTUSDT', '1m', last_datetime, end_date)
    if new_df is None:
        break
    df_list.append(new_df)
    last_datetime = max(new_df.index) + dt.timedelta(0, 1)
    count+=1
    if count >= 68:
        break


df = pd.concat(df_list)
df.shape
csv_file_path = "data_1min/dot_usd_1min_data6.csv"
df.to_csv(csv_file_path)
print(df)
count = 0
df_list = []
last_datetime = dt.datetime(2024, 7, 1)
end_date = dt.datetime(2024, 7, 29)
while True:
    new_df = get_binance_bars('SOLUSDT', '1m', last_datetime, end_date)
    if new_df is None:
        break
    df_list.append(new_df)
    last_datetime = max(new_df.index) + dt.timedelta(0, 1)
    count+=1
    if count >= 68:
        break


df = pd.concat(df_list)
df.shape
csv_file_path = "data_1min/sol_usd_1min_data6.csv"
df.to_csv(csv_file_path)
print(df)
