# Import everything
import time
from loadAPI import getSubKey
import pandas as pd
import pandas_ta as ta
import ccxt
import datetime as dt
from collections import deque

api_key = '55d0904d-6270-475d-98a1-c99b0d9413da'
secret = 'KUPMfNVJxjA_A-IIDiGmG5c8RECraTiLfjijsqS2FJQ3MjUzMzNlNy04OWRmLTRmMGQtOWZhMS1kNTUwYzQzZjJkOWE'
exchange = ccxt.phemex({
    'apiKey': api_key,
    'secret': secret,
    'options': {'defaultType': 'swap'}
})
symbols = ['SOL/USDT:USDT', 'MATIC/USDT:USDT', 'APT/USDT:USDT']
symbols_queue = deque(symbols)

def place_orders(prices, size, type, symbol):
    if type == 'buy':
        multi = 0.9999
    else:
        multi = 1.0001
    try:
        order = exchange.create_order(symbol, 'market', side=type, amount=size, price=None, params={
            'stopLoss': {
                'triggerPrice': prices[2],
                'type': 'market',
            },
            'takeProfit': {
                'triggerPrice': prices[1] * multi,
                'type': 'limit',
                'price': prices[1],
            },
        })
        print(f"Market order placed: {order['id']}")
        date = dt.datetime.now()
        with open('X1_log.txt', 'a') as file:
            file.write(f'{date}   {symbol}   EP: {prices[0]} SL: {prices[2]} TP: {prices[1]} Type: {type} Size: {size}\n')
        return order
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        return None


def check_for_trades(symbol, df, risk, ready_for_trade):
    if ready_for_trade == 1:
        if df['rsi'].iloc[-1] > 80 + 0:
            ready_for_trade = 3
    elif ready_for_trade == 2:
        if df['rsi'].iloc[-1] < 20 - 0:
            ready_for_trade = 4
    elif ready_for_trade == 3:
        if 0 < df['MACDh_98_99_30'].iloc[-1] < df['MACDh_98_99_30'].iloc[-2] and df['rsi'].iloc[-1] < 80:
            if df['MACDh_98_99_30'].iloc[-2] < df['MACDh_98_99_30'].iloc[-3]:
                ready_for_trade = 0
            else:
                SL = df['rolling_high'].iloc[-1] * (1 + 0.005)
                ob = exchange.fetch_order_book(symbol)
                EP = float(ob['asks'][0][0])
                if abs(SL - EP) / EP < 0.001:
                    ready_for_trade = 0
                else:
                    TP = (EP - SL) * 2.5 + EP
                    Entry_size = risk / (SL - EP)
                    place_orders([EP, TP, SL], Entry_size, 'sell', symbol)
                    ready_for_trade = 0
    elif ready_for_trade == 4:
        if 0 > df['MACDh_98_99_30'].iloc[-1] > df['MACDh_98_99_30'].iloc[-2] and df['rsi'].iloc[-1] > 20:
            if df['MACDh_98_99_30'].iloc[-2] > df['MACDh_98_99_30'].iloc[-3]:
                ready_for_trade = 0
            else:
                SL = df['rolling_low'].iloc[-1] * (1 - 0.005)
                ob = exchange.fetch_order_book(symbol)
                EP = float(ob['bids'][0][0])
                if abs(SL - EP) / SL < 0.001:
                    ready_for_trade = 0
                else:
                    TP = (EP - SL) * 2.5 + EP
                    Entry_size = risk / (EP - SL)
                    place_orders([EP, TP, SL], Entry_size, 'buy', symbol)
                    ready_for_trade = 0
    if ready_for_trade < 3:
        if df['high'].iloc[-1] >= df['BBU_20_2.0'].iloc[-1]:
            ready_for_trade = 1
        elif df['low'].iloc[-1] <= df['BBL_20_2.0'].iloc[-1]:
            ready_for_trade = 2
    return ready_for_trade


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
    data = exchange.fetch_ohlcv(symbol=symbol, timeframe='1m', limit=1000)
    df = pd.DataFrame(data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    return df


def end_trade(symbol, prev_size, accountSize):
    profit = accountSize-prev_size
    date = dt.datetime.now()
    if profit > 0:
        win = 'WIN'
    else:
        win = 'LOSS'
    with open('X1_log.txt', 'a') as file:
        file.write(f'{date}   {symbol}   {win}  PnL: ${profit}\n')
    return check_past_data(symbol)

def add_EMAs(df):
    df['ohlc4'] = (df['open']+df['high']+df['low']+df['close'])/4
    df['rsi'] = ta.rsi(df['close'], length=14)

    # Calculate Bollinger Bands
    bb = ta.bbands(df['close'], length=20, std=2)
    df = df.join(bb)

    # Calculate MACD
    macd = ta.macd(df['close'], fast=98, slow=99, signal=30)
    df = df.join(macd)

    # Print the latest values
    df['rolling_high'] = df['close'].rolling(window=14).max()
    df['rolling_low'] = df['close'].rolling(window=14).min()
    return df

def check_for_entry(orders, all_orders, EP, L1, Entry_size, type, symbol):
    pass

def check_past_data(symbol):
    data = fetch_historical_data(symbol)
    data = add_EMAs(data)
    ready_for_trade = 0
    for i in range(-15, -2):
        df = data[:(1000 + i)].copy()
        if ready_for_trade == 1:
            if df['rsi'].iloc[-1] > 80 + 3:
                ready_for_trade = 3
        elif ready_for_trade == 2:
            if df['rsi'].iloc[-1] < 20 - 3:
                ready_for_trade = 4
        elif ready_for_trade == 3:
            if 0 < df['MACDh_98_99_30'].iloc[-1] < df['MACDh_98_99_30'].iloc[-2] and df['rsi'].iloc[-1] < 80:
                ready_for_trade = 0
        elif ready_for_trade == 4:
            if 0 > df['MACDh_98_99_30'].iloc[-1] > df['MACDh_98_99_30'].iloc[-2] and df['rsi'].iloc[-1] > 20:
                ready_for_trade = 0
        if ready_for_trade == 0:
            if df['high'].iloc[-1] >= df['BBU_20_2.0'].iloc[-1]:
                ready_for_trade = 1
            elif df['low'].iloc[-1] <= df['BBL_20_2.0'].iloc[-1]:
                ready_for_trade = 2
    return ready_for_trade

# Error Handling
# Check if there are orders/positions on startup
def main():
    # Replace with your API keys
    api_key = '55d0904d-6270-475d-98a1-c99b0d9413da'
    secret = 'KUPMfNVJxjA_A-IIDiGmG5c8RECraTiLfjijsqS2FJQ3MjUzMzNlNy04OWRmLTRmMGQtOWZhMS1kNTUwYzQzZjJkOWE'
    exchange = ccxt.phemex({
        'apiKey': api_key,
        'secret': secret,
        'options': {'defaultType': 'swap'}
    })
    # symbols = ['SOL/USDT:USDT', 'MATIC/USDT:USDT', 'APT/USDT:USDT']
    # symbols_queue = deque(symbols)
    symbol = 'SOL/USDT:USDT'
    compound = False
    Entry = None
    in_position = False
    prices = []
    stored_sizes = []
    Entry_size = 0
    TP = 0
    SL = 0
    EP = 0
    risk_amount = 2
    ready_for_trade = 0
    prev_size = 0
    type = 'buy'
    #for symbol in symbols:
    exchange.set_position_mode(hedged=False, symbol=symbol)
    exchange.set_leverage(20, symbol)
    ready_for_trade = check_past_data(symbol)
        # reset_orders(symbol)
    while True:
        # symbol = symbols_queue.pop()
        df = fetch_historical_data(symbol)
        df = add_EMAs(df)
        current_time = dt.datetime.now().time()
        print(symbol)
        print(current_time)
        bal = exchange.fetch_balance()
        accountSize = float(bal['info']['data']['account']['accountBalanceRv'])
        pos_size = exchange.fetch_positions([symbol])[0]['info']['size']
        if pos_size == '0':
            if in_position:
                ready_for_trade = end_trade(symbol, prev_size, accountSize)
                in_position = False
            else:
                ready_for_trade = check_for_trades(symbol, df, risk_amount, ready_for_trade)
                prev_size = accountSize
        else:
            in_position = True
        #if ready_for_trade == 0:
            #symbols_queue.appendleft(symbol)
        #else:
            #symbols_queue.append(symbol)
        print(ready_for_trade)
        print(symbols_queue)
        print("waiting 5 seconds")
        time.sleep(5)

if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print(e)
            time.sleep(30)
