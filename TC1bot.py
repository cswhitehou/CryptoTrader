# Import everything
import time

from loadAPI import getSubKey
import pandas as pd
import backtrader as bt
import numpy as np
import ccxt
import backtrader.feeds as btfeeds
import datetime as dt
from collections import deque

api_key, secret = getSubKey()
exchange = ccxt.phemex({
    'apiKey': api_key,
    'secret': secret,
    'options': {'defaultType': 'swap'}
})
symbols = ['MATIC/USDT:USDT', 'LINK/USDT:USDT', 'SOL/USDT:USDT', 'APT/USDT:USDT', 'DOT/USDT:USDT', 'ADA/USDT:USDT', 'ATOM/USDT:USDT', 'XRP/USDT:USDT']
symbols_queue = deque(symbols)


def find_fair_value_gaps(df):
    gaps = []
    for i in range(-2, -74):
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            gaps.append((df['low'].iloc[i], df['high'].iloc[i - 2], df['low'].iloc[i]-df['high'].iloc[i - 2], (df['low'].iloc[i]+df['high'].iloc[i - 2])/2, 'bullish'))
        elif df['low'].iloc[i-2] > df['high'].iloc[i]:
            gaps.append((df['low'].iloc[i-2], df['high'].iloc[i], df['low'].iloc[i-2]-df['high'].iloc[i], (df['low'].iloc[i]+df['high'].iloc[i - 2])/2, 'bearish'))
    return gaps

def find_support_resistance(df, window=4):
    SR = []
    for i in range(window, len(df) - window):
        if df['low'].iloc[i] == df['low'].iloc[i - window:i + window + 1].min():
            SR.append(df['low'].iloc[i])
        if df['high'].iloc[i] == df['high'].iloc[i - window:i + window + 1].max():
            SR.append(df['high'].iloc[i])
    return SR


def add_support_resistance(df, supports, resistances):
    df['Support'] = 0
    df['Resistance'] = 0
    for group in supports:
        df.loc[group[0], 'Support'] = 1
    for group in resistances:
        df.loc[group[0], 'Resistance'] = 1
    return df


def place_orders(prices, size, type, symbol):
    try:
        order = exchange.create_limit_order(symbol, side=type, amount=size, price=prices[0], params={
            'stopLoss': {
                'triggerPrice': prices[2],
                'type': 'market',
            },
            'takeProfit': {
                'triggerPrice': prices[1],
                'type': 'limit',
                'price': prices[1],
            },
        })
        print(f"Limit order placed: {order['id']}")
        return order
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        return None


def check_for_trades(df, SR, FVGs, risk, type, trend):
    print("Checking for trade")
    print(f"HIGH: {df['high'].iloc[-1]} LOW: {df['low'].iloc[-1]}")
    print(f"ROLLING HIGH: {df['rolling_high'].iloc[-1]} ROLLING LOW: {df['rolling_low'].iloc[-1]}")
    #if df['EMA_20'].iloc[0] > df['EMA_50'].iloc[0] > df['EMA_200'].iloc[0]:
    if df['high'].iloc[-1] == df['rolling_high'].iloc[-1]:
        print("passed 1 long")
        trend_high = df['high'].iloc[-1]
# Find most recent support for the low
        for i in range(6, 48):
            window_low = df['low'].iloc[-i - 8:-i + 8 + 1].min()
            if df['low'].iloc[-i] == window_low:
                print("passed 2 long")
                trend_low = df['low'].iloc[-i]
                if 0.015 < (trend_high - trend_low) / trend_low < 0.05:
                    EP = (trend_high - trend_low) * 0.382 + trend_low
                    SL = (trend_high - trend_low) * 0.17 + trend_low
                    TP = (trend_high - trend_low) * 1.272 + trend_low
                    sr_count = 0
                    for j in range(4, i):
                        window_small_low = df['low'].iloc[-j - 4:-j + 4 + 1].min() # Make sure this works as desired
                        window_small_high = df['high'].iloc[-j - 4:-j + 4 + 1].max()
                        if EP * (1 + 0.0007) > df['low'].iloc[-j] > EP * (1 - 0.0007) and \
                                df['low'].iloc[-j] == window_small_low:
                            sr_count += 1
                        if EP * (1 + 0.0007) > df['high'].iloc[-j] > EP * (1 - 0.0007) and \
                                df['high'].iloc[-j] == window_small_high:
                            sr_count += 1
                    # print(self.SR)
                    for sr in SR:
                        if EP * (1 + 0.001) > sr > EP * (1 - 0.001):
                            sr_count += 1
                    if sr_count >= 2: # and (self.ema200 > self.SL or self.ema_200_check):
                        print("passed 3 long")
                        for fvg in FVGs:
                            if SL < fvg[3] < EP:
                                print("passed 4 long")
                                # print(f"E: {self.EP}, TP: {self.TP}, SL: {self.SL}, High: {self.trend_high}, Low: {self.trend_low}")
                                # Calculate Entry, L1, and L2 position size so L1 avg cost is at 0.441 and L2 at 0.29
                                # 35% Account risk on 50x leverage
                                Entry_size = risk / (EP - SL)
                                # Check to see if we are in the time range. If so, store the order instead of placing it
                                # if (dt.time(0, 0) <= current_time and current_time < dt.time(9, 0)):
                                # self.stored_trade = (
                                # 'buy', self.EP, self.Entry_size, self.TP, self.SL)
                                # print("Long trade setup stored")
                                # else:
                                # self.Entry = self.buy(exectype=bt.Order.Limit, price=self.EP,
                                #                       size=self.Entry_size)
                                # print("Long Order placed")
                                type = 'buy'
                                Entry = place_orders([EP, TP, SL], Entry_size, type, symbol)
                                return Entry, type, trend_high

#elif df['EMA_20'].iloc[0] > df['EMA_50'].iloc[0] > df['EMA_200'].iloc[0]:
    elif df['low'].iloc[-1] == df['rolling_low'].iloc[-1]:
        print("passed 1 short")
        trend_low = df['low'].iloc[-1]
        # Find most recent support for the low
        for i in range(6, 48):
            window_high = df['high'].iloc[-i - 8:-i + 8 + 1].max()
            if df['high'].iloc[-i] == window_high:
                print("passed 2 short")
                trend_high = df['high'].iloc[-i]
                # if not (self.rsi < self.prev_rsi < 70):
                if 0.015 < (trend_high - trend_low) / trend_high < 0.05:
                    EP = (trend_low - trend_high) * 0.382 + trend_high
                    SL = (trend_low - trend_high) * 0.17 + trend_high
                    TP = (trend_low - trend_high) * 1.272 + trend_high
                    sr_count = 0
                    for j in range(4, i):
                        window_small_low = df['low'].iloc[-j - 4:-j + 4 + 1].min() # Make sure this works as desired
                        window_small_high = df['high'].iloc[-j - 4:-j + 4 + 1].max()
                        if EP * (1 + 0.0007) > df['low'].iloc[-j] > EP * (1 - 0.0007) and df['low'].iloc[-j] == window_small_low:
                            sr_count += 1
                        if EP * (1 + 0.0007) > df['high'].iloc[-j] > EP * (1 - 0.0007) and df['high'].iloc[-j] == window_small_high:
                            sr_count += 1
                    # print(self.SR)
                    for sr in SR:
                        if EP * (1 + 0.001) > sr > EP * (1 - 0.001):
                            sr_count += 1
                    if sr_count >= 2: #(self.ema200 < self.SL or self.ema_200_check):
                        print("passed 3 short")
                        for fvg in FVGs:
                            if SL < fvg[3] < EP:
                                print("passed 4 short")
                                # print(f"E: {self.EP}, TP: {self.TP}, SL: {self.SL}, High: {self.trend_high}, Low: {self.trend_low}")
                                # Calculate Entry, L1, and L2 position size so L1 avg cost is at 0.441 and L2 at 0.29
                                # 35% Account risk on 50x leverage
                                Entry_size = risk / (SL - EP)
                                # Check to see if we are in the time range. If so, store the order instead of placing it
                                # if (dt.time(0, 0) <= current_time and current_time < dt.time(9, 0)):
                                # self.stored_trade = (
                                # 'buy', self.EP, self.Entry_size, self.TP, self.SL)
                                # print("Long trade setup stored")
                                # else:
                                # self.Entry = self.buy(exectype=bt.Order.Limit, price=self.EP,
                                #                       size=self.Entry_size)
                                # print("Long Order placed")
                                type = 'sell'
                                Entry = place_orders([EP, TP, SL], Entry_size, type, symbol)
                                return Entry, type, trend_low
    return None, type, trend


def check_for_new_high(type, trend, Entry):
    if type == 'buy':
        if Entry is not None:
            if df.high.iloc[-1] > trend:
                print("New High")
                return reset_orders(symbol)
    if type == 'sell':
        if Entry is not None:
            if df.low.iloc[-1] < trend:
                print("New Low")
                return reset_orders(symbol)
    return Entry


def reset_orders(symbol):
    pos_size = exchange.fetch_positions([symbol])[0]['info']['size']
    pos_side = exchange.fetch_positions([symbol])[0]['info']['side']
    if pos_size != 0:
        print(pos_size)
        print(pos_side)
        if pos_side == 'Sell':
            exchange.create_order(symbol, 'market', 'buy', pos_size, params={'reduceOnly': True})
        elif pos_side == 'Buy':
            exchange.create_order(symbol, 'market', 'sell', pos_size, params={'reduceOnly': True})
    exchange.cancel_all_orders(symbol)
    exchange.cancel_all_orders(symbol=symbol, params={'untriggered': True})
    print("Orders Canceled")
    return None


def fetch_historical_data(symbol):
    data = exchange.fetch_ohlcv(symbol=symbol, timeframe='5m', limit=1000)
    data15 = exchange.fetch_ohlcv(symbol=symbol, timeframe='15m', limit=1000)
    data1h = exchange.fetch_ohlcv(symbol=symbol, timeframe='1h', limit=1000)
    df = pd.DataFrame(data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df15 = pd.DataFrame(data15, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df1h = pd.DataFrame(data1h, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    return df, df15, df1h


def add_EMAs(df):
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['rolling_high'] = df['high'].rolling(window=12 * 4).max()
    df['rolling_low'] = df['low'].rolling(window=12 * 4).min()
    return df

def check_for_entry(orders, all_orders, EP, L1, Entry_size, type, symbol):
    pass


def check_historical_trades(symbol, risk_amount):
    trade_check = 0
    df, df15, df1h = fetch_historical_data(symbol)
    supports, resistances = find_support_resistance(df, 52)
    df = add_support_resistance(df, supports, resistances)
    type = 'buy'
    trend = 0
    stored_prices = []
    stored_sizes = []
    prices = []
    sizes = []
    FVGs = find_fair_value_gaps(df1h)
    SR = find_support_resistance(df15, 3)
    for i in range(-250, -1):
        data = df[:(1000+i)].copy()
        data15 = df15[:(1000+i//4)].copy()
        data1h = df1h[:(1000+i//12)].copy()
        data = add_EMAs(data)
        if len(stored_prices) > 0:
            if type == 'buy':
                if data['high'].iloc[-1] > trend:
                    print("New High")
                    stored_prices = []
                    stored_sizes = []
            if type == 'sell':
                if data['low'].iloc[-1] < trend:
                    print("New Low")
                    stored_prices = []
                    stored_sizes = []
        Entry, type, trend = check_for_trades(df, SR, FVGs, risk_amount, type, trend)
        # print(prices)
        # print(type)
        if len(prices) > 0:
            stored_prices = prices
            stored_sizes = sizes
            print(stored_prices)
        stored_prices, trade_check = trade_completion_check(stored_prices, trade_check, type,  data)
    return stored_prices, stored_sizes, type, trend


def trade_completion_check(stored_prices, trade_check, type, df):
    pass
# Error Handling
# Check if there are orders/positions on startup
if __name__ == '__main__':
    # Replace with your API keys
    api_key, secret = getSubKey()
    exchange = ccxt.phemex({
        'apiKey': api_key,
        'secret': secret,
        'options': {'defaultType': 'swap'}
    })
    compound = False
    Entry = None
    in_position = False
    prices = []
    stored_sizes = []
    Entry_size = 0
    TP = 0
    SL = 0
    EP = 0
    risk_amount = 5
    trend = 0
    type = 'buy'
    for symbol in symbols:
        exchange.set_position_mode(hedged=False, symbol=symbol)
        exchange.set_leverage(-50, symbol)
        # reset_orders(symbol)
    """for i in range(len(symbols)):
        symbol = symbols_queue.popleft()
        symbols_queue.append(symbol)
        print(symbol)
        print(symbols_queue)
        stored_prices, sizes, type, trend = check_historical_trades(symbol)
        print(sizes)
        print(stored_prices)
        if len(sizes) > 0:
            stored_sizes = sizes
            stored_prices.append(symbol)
            break"""
    while True:
        symbol = symbols_queue.pop()
        df, df15, df1h = fetch_historical_data(symbol)
        df = add_EMAs(df)
        FVGs = find_fair_value_gaps(df1h)
        SR = find_support_resistance(df15, 3)
        current_time = dt.datetime.now().time()
        print(symbol)
        print(current_time)
        # bal = exchange.fetch_balance()
        # accountSize = bal['info']['data']['account']['accountBalanceRv']
        pos_size = exchange.fetch_positions([symbol])[0]['info']['size']
        if pos_size == '0':
            if Entry is not None:
                Entry = check_for_new_high(type, trend, Entry)
            if Entry is None:
                Entry, type, trend = check_for_trades(df, SR, FVGs, risk_amount, type, trend)
            symbols_queue.appendleft(symbol)
            print(symbols_queue)
        else:
            symbols_queue.append(symbol)
        print("waiting 20 seconds")
        time.sleep(20)
