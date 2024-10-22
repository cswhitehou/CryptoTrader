# Colby Whitehouse
# 7/23/2024
# This is a python bot that uses an algorithm to trade cryptocurrencies on phemex

# Import everything
import time
import threading
import pandas as pd
import pandas_ta as ta
import ccxt
import datetime as dt
from collections import deque
import logging
import smtplib
from email.mime.text import MIMEText
import atexit

api_key = ''
secret = ''
exchange = ccxt.phemex({
    'apiKey': api_key,
    'secret': secret,
    'options': {'defaultType': 'swap'}
})
symbols = ['SOL/USDT:USDT', 'MATIC/USDT:USDT', 'DOT/USDT:USDT']
symbols_queue = deque(symbols)

logging.basicConfig(filename='trading_bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# This function sends an SMS message by email to the phone number that is used as the input
def send_sms_via_email(phone_number, carrier_gateway, message):
    # Your email credentials
    email = ""
    password = ""

    # Setup the MIME
    msg = MIMEText(message)
    msg['From'] = email
    msg['To'] = f"{phone_number}@{carrier_gateway}"
    msg['Subject'] = "Trade Notification"

    # Sending the email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email, password)
            server.sendmail(email, f"{phone_number}@{carrier_gateway}", msg.as_string())
        print("SMS sent successfully!")
    except Exception as e:
        print(f"Failed to send SMS: {e}")

# This is called to reset orders if the program fails and has to exit
def on_exit():
    send_sms_via_email("", "", 'Phemex Bot Stopped')
    for symbol in symbols:
        reset_orders(symbol)

# Places orders if the conditions are met to enter a trade
def place_orders(prices, size, type, symbol):

    try:
        order = exchange.create_limit_order(symbol, side=type, amount=size, price=prices[0])
        date = dt.datetime.now()
        with open('X1_log.txt', 'a') as file:
            message = f'{date}   {symbol}   EP: {prices[0]} SL: {prices[2]} TP: {prices[1]} Type: {type} Size: {size}\n'
            file.write(message)
        send_sms_via_email("", "", message)
        if type == 'buy':
            multi = 0.9999
            new_type = 'sell'
        else:
            multi = 1.0001
            new_type = 'buy'
        tp_params = {
            'ordType': 'LimitIfTouched',
            'triggerType': 'ByLastPrice',
            'stopPxRp': prices[1] * multi
        }
        exchange.create_order(symbol, 'limit', new_type, size, prices[1], params=tp_params)
        sl_params = {
            'ordType': 'Stop',
            'triggerType': 'ByLastPrice',
            'stopPxRp': prices[2]
        }
        exchange.create_order(symbol, 'market', new_type, size, prices[2], params=sl_params)
        return order
    except ccxt.BaseError as e:
        logging.error(f"An error occurred: {str(e)}")
        reset_orders(symbol)
        return None

# This is the main logic which checks if a trade should be entered
def check_for_trades(symbol, df, risk, ready_for_trade, trend, type):
    if ready_for_trade == 1:
        if df['rsi'].iloc[-1] > 80 + 0:
            ready_for_trade = 3
    elif ready_for_trade == 2:
        if df['rsi'].iloc[-1] < 20 - 0:
            ready_for_trade = 4
    # SHORT
    elif ready_for_trade == 3:
        if 0 < df['MACDh_98_99_30'].iloc[-1] < df['MACDh_98_99_30'].iloc[-2] and df['rsi'].iloc[-1] < 80:
            if df['MACDh_98_99_30'].iloc[-2] < df['MACDh_98_99_30'].iloc[-3]:
                ready_for_trade = 0
            else:
                SL = df['rolling_high'].iloc[-1] * (1 + 0.005)
                ob = exchange.fetch_order_book(symbol)
                EP = float(ob['asks'][1][0])
                if abs(SL - EP) / EP < 0.001:
                    ready_for_trade = 0
                else:
                    TP = (EP - SL) * 2.6 + EP
                    Entry_size = risk / (SL - EP)
                    trend = (EP - SL) + EP
                    type = 'sell'
                    place_orders([EP, TP, SL], Entry_size, type, symbol)
                    ready_for_trade = 5
    # LONG
    elif ready_for_trade == 4:
        if 0 > df['MACDh_98_99_30'].iloc[-1] > df['MACDh_98_99_30'].iloc[-2] and df['rsi'].iloc[-1] > 20:
            if df['MACDh_98_99_30'].iloc[-2] > df['MACDh_98_99_30'].iloc[-3]:
                ready_for_trade = 0
            else:
                SL = df['rolling_low'].iloc[-1] * (1 - 0.005)
                ob = exchange.fetch_order_book(symbol)
                EP = float(ob['bids'][1][0])
                if abs(SL - EP) / SL < 0.001:
                    ready_for_trade = 0
                else:
                    TP = (EP - SL) * 2.6 + EP
                    Entry_size = risk / (EP - SL)
                    trend = (EP - SL) + EP
                    type = 'buy'
                    place_orders([EP, TP, SL], Entry_size, type, symbol)
                    ready_for_trade = 5
    if ready_for_trade < 3:
        if df['high'].iloc[-1] >= df['BBU_20_2.0'].iloc[-1]:
            ready_for_trade = 1
        elif df['low'].iloc[-1] <= df['BBL_20_2.0'].iloc[-1]:
            ready_for_trade = 2
    return ready_for_trade, trend, type

# This function resets the orders and takes us out of the position
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
    logging.info(f"Orders Canceled for {symbol}")
    return

# This function gets the candle data from phemex
def fetch_historical_data(symbol):
    data = exchange.fetch_ohlcv(symbol=symbol, timeframe='1m', limit=1000)
    df = pd.DataFrame(data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    return df

# This function is called after a trade is complete to log the trade data in a csv
def end_trade(symbol, prev_size, accountSize, type):
    if type == 'buy':
        dir = 'LONG'
    else:
        dir = 'SHORT'
    profit = accountSize-prev_size
    date = dt.datetime.now()
    if profit > 0:
        win = 'WIN'
    else:
        win = 'LOSS'
    with open('X1_results.csv', 'a') as file:
        message = f'{date},{symbol},{win},{dir},${profit:.2f},${accountSize:.2f}\n'
        file.write(message)
    send_sms_via_email("", "", message)
    return check_past_data(symbol)

# This function adds the other indicators to the data
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

# This checks if the price misses entry and creates a new high/low
def check_for_new_high(symbol, df, type, trend):
    if type == 'buy':
        if df.high.iloc[-1] > trend:
            logging.info("New High detected, resetting orders")
            reset_orders(symbol)
            return 0
    if type == 'sell':
        if df.low.iloc[-1] < trend:
            logging.info("New Low detected, resetting orders")
            reset_orders(symbol)
            return 0
    return 5

# This checks for trades for the past 15 mins and is called when the program starts up or after a trade is completed
def check_past_data(symbol):
    data = fetch_historical_data(symbol)
    data = add_EMAs(data)
    ready_for_trade = 0
    for i in range(-15, -2):
        df = data[:(1000 + i)].copy()
        if ready_for_trade == 1:
            if df['rsi'].iloc[-1] > 80:
                ready_for_trade = 3
        elif ready_for_trade == 2:
            if df['rsi'].iloc[-1] < 20:
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

# The main logic for the trading bot which uses a while loop inside of try/except logic
def trade_symbol(symbol):
    # Replace with your API keys
    api_key = ''
    secret = ''
    exchange = ccxt.phemex({
        'apiKey': api_key,
        'secret': secret,
        'options': {'defaultType': 'swap'}
    })
    trend = 0
    logging.info(f'Starting trading for {symbol}')
    risk_amount = 10
    prev_size = 0
    type = 'buy'
    in_position = False
    exchange.set_position_mode(hedged=False, symbol=symbol)
    exchange.set_leverage(20, symbol)
    ready_for_trade = check_past_data(symbol)
    while True:
        try:
            df = fetch_historical_data(symbol)
            df = add_EMAs(df)
            current_time = dt.datetime.now().time()
            print(symbol)
            print(current_time)
            bal = exchange.fetch_balance()
            accountSize = float(bal['info']['data']['account']['accountBalanceRv'])
            # pos_size = exchange.fetch_positions([symbol])[0]['info']['size']
            orders = exchange.fetch_open_orders(symbol)
            if len(orders) == 2:
                if in_position == False:
                    send_sms_via_email("", "", f'Limit order filled for {symbol}')
                in_position = True
                ready_for_trade = 0
            else:
                if len(orders) == 3:
                    ready_for_trade = check_for_new_high(symbol, df, type, trend)
                elif len(orders) == 1:
                    in_position = False
                    reset_orders(symbol)
                    ready_for_trade = end_trade(symbol, prev_size, accountSize, type)
                else:
                    ready_for_trade, trend, type = check_for_trades(symbol, df, risk_amount, ready_for_trade, trend, type)
                    prev_size = accountSize
        except Exception as e:
            logging.error(f"Unexpected error in trade loop for {symbol}: {str(e)}")
            time.sleep(30)
        print(ready_for_trade)
        time.sleep(5)

# MAIN function that creates the threads so each token can be traded in parallel
if __name__ == '__main__':
    atexit.register(on_exit)
    send_sms_via_email("", "", 'Phemex Bot Running')
    threads = []
    for symbol in symbols:
        t = threading.Thread(target=trade_symbol, args=(symbol,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
