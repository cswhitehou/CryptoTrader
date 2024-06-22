# Import everything
import time
from loadAPI import getKey
import pandas as pd
import ccxt
import datetime as dt
from collections import deque

api_key, secret = getKey()
exchange = ccxt.phemex({
    'apiKey': api_key,
    'secret': secret,
    'options': {'defaultType': 'swap'}
})
symbols = ['MATIC/USDT:USDT', 'XRP/USDT:USDT', 'DOT/USDT:USDT', 'SOL/USDT:USDT', 'LINK/USDT:USDT']
symbols_queue = deque(symbols)


def find_support_resistance(df, window=4):
    supports = []
    resistances = []
    for i in range(window, len(df) - window):
        if df['low'].iloc[i] == df['low'].iloc[i - window:i + window + 1].min():
            supports.append((df.index[i], df['low'].iloc[i]))
        if df['high'].iloc[i] == df['high'].iloc[i - window:i + window + 1].max():
            resistances.append((df.index[i], df['high'].iloc[i]))
    return supports, resistances


def add_support_resistance(df, supports, resistances):
    df['Support'] = 0
    df['Resistance'] = 0
    for group in supports:
        df.loc[group[0], 'Support'] = 1
    for group in resistances:
        df.loc[group[0], 'Resistance'] = 1
    return df
"""def place_orders(prices, sizes, type, symbol):
    orders = []
    try:
        order = exchange.create_limit_order(symbol, side=type, amount=sizes[0], price=prices[0], params={
        'takeProfit': {
            'triggerPrice': prices[3],
            'type': 'limit',
            'price': prices[3],
        },
    })
        print(f"Limit order placed: {order['id']}")
        orders.append(order['id'])
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        return None
    try:
        order = exchange.create_limit_order(symbol, side=type, amount=sizes[1], price=prices[1], params={
        'takeProfit': {
            'triggerPrice': prices[0],
            'type': 'limit',
            'price': prices[0],
        },
    })
        print(f"Limit order placed: {order['id']}")
        orders.append(order['id'])
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        return None
    try:
        order = exchange.create_limit_order(symbol, side=type, amount=sizes[2], price=prices[2], params={
        'stopLoss': {
            'triggerPrice': prices[4],
            'type': 'market',
        },
        'takeProfit': {
            'triggerPrice': prices[1],
            'type': 'limit',
            'price': prices[1],
        },
    })
        print(f"Limit order placed: {order['id']}")
        orders.append(order['id'])
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        return None
    return orders"""

def place_orders(prices, sizes, type, symbol):
    orders = []
    try:
        order = exchange.create_limit_order(symbol, side=type, amount=sizes[0], price=prices[0])
        print(f"Limit order placed: {order['id']}")
        orders.append(order['id'])
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        reset_orders(symbol)
        return []
    try:
        order = exchange.create_limit_order(symbol, side=type, amount=sizes[1], price=prices[1])
        print(f"Limit order placed: {order['id']}")
        orders.append(order['id'])
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        reset_orders(symbol)
        return []
    try:
        order = exchange.create_limit_order(symbol, side=type, amount=sizes[2], price=prices[2])
        print(f"Limit order placed: {order['id']}")
        orders.append(order['id'])
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        reset_orders(symbol)
        return []
    if type == 'buy':
        orders = place_take_profit_order(sizes[0], prices[3], orders, 'sell', symbol)
        orders = place_stop_loss_order(9 * sizes[0], prices[4], orders, 'sell', symbol)
    elif type == 'sell':
        orders = place_take_profit_order(sizes[0], prices[3], orders, 'buy', symbol)
        orders = place_stop_loss_order(9 * sizes[0], prices[4], orders, 'buy', symbol)
    return orders


def check_for_trades(df, df15, df1h, compound, accountSize, risk, type, trend):
    EMA_15m = df15['close'].ewm(span=200, adjust=False).mean().iloc[-1]
    EMA_1h = df1h['close'].ewm(span=200, adjust=False).mean().iloc[-1]
    if df['EMA_20'].iloc[-1] > df['EMA_50'].iloc[-1] > df['EMA_200'].iloc[-1]:
        # print("passed 1 Long")
        if df['high'].iloc[-1] > EMA_15m and df['high'].iloc[-1] > EMA_1h:
            # print('passed 2 Long')
            if df['high'].iloc[-1] == df['rolling_high'].iloc[-1]:
                # print("passed 3 Long")
                trend_high = df['high'].iloc[-1]                        ####
                for i in range(-432, -144):
                    window_low2 = df['low'].iloc[i-10:].min()
                    if df['Support'].iloc[i] == 1 and df['low'].iloc[i] == window_low2:
                        too_steep = 0
                        for j in range(-600, -16):
                            if (df['high'].iloc[j + 16] - df['low'].iloc[j]) / df['low'].iloc[j] > 0.055:
                                too_steep = 1
                        if too_steep == 0:
                            print("passed 4 Long")
                            if 0.04 < (trend_high - df['low'].iloc[i]) / df['low'].iloc[i] < 0.09:
                                print("Long Opportunity")
                                trend_low = df['low'].iloc[i]
                                EP = (trend_high - trend_low) * 0.618 + trend_low
                                L1 = (trend_high - trend_low) * 0.382 + trend_low
                                L2 = (trend_high - trend_low) * 0.17 + trend_low
                                SL = -(trend_high - trend_low) * 0.05 + trend_low
                                TP = (trend_high - trend_low) * 1.272 + trend_low
                                if compound:
                                    Entry_size = (accountSize * risk) / (
                                                EP + 3 * L1 + 5 * L2 - 9 * SL)
                                else:
                                    Entry_size = 20 / (EP + 3 * L1 + 5 * L2 - 9 * SL)
                                Limit1_size = 3 * Entry_size
                                Limit2_size = 5 * Entry_size
                                return [EP, L1, L2, TP, SL], [Entry_size, Limit1_size, Limit2_size], 'buy', trend_high
    if df['EMA_20'].iloc[-1] < df['EMA_50'].iloc[-1] < df['EMA_200'].iloc[-1]:
        # print("passed 1 short")
        if df['low'].iloc[-1] < EMA_15m and df['low'].iloc[-1] < EMA_1h:
            # print("passed 2 short")
            # print(df['low'].iloc[-1])
            # print(df['rolling_low'].iloc[-1])
            if df['low'].iloc[-1] == df['rolling_low'].iloc[-1]:
                # print("passed 3 short")
                trend_low = df['low'].iloc[-1]                        ####
                for i in range(-432, -144):
                    window_high2 = df['high'].iloc[i-10:].max()
                    if df['Resistance'].iloc[i] == 1 and df['high'].iloc[i] == window_high2:
                        too_steep = 0
                        for j in range(-600, -16):
                            if (df['high'].iloc[j] - df['low'].iloc[j + 16]) / df['high'].iloc[j] > 0.055:
                                too_steep = 1
                        if too_steep == 0:
                            print("passed 4 short")
                            if 0.04 < (df['high'].iloc[i] - trend_low) / df['high'].iloc[i] < 0.09:
                                print("Short Opportunity")
                                trend_high = df['high'].iloc[i]
                                EP = (trend_low - trend_high) * 0.618 + trend_high
                                L1 = (trend_low - trend_high) * 0.382 + trend_high
                                L2 = (trend_low - trend_high) * 0.17 + trend_high
                                SL = -(trend_low - trend_high) * 0.05 + trend_high
                                TP = (trend_low - trend_high) * 1.272 + trend_high
                                if compound:
                                    Entry_size = abs((accountSize * risk) / (
                                                EP + 3 * L1 + 5 * L2 - 9 * SL))
                                else:
                                    Entry_size = abs(20 / (EP + 3 * L1 + 5 * L2 - 9 * SL))
                                Limit1_size = 3 * Entry_size
                                Limit2_size = 5 * Entry_size
                                return [EP, L1, L2, TP, SL], [Entry_size, Limit1_size, Limit2_size], 'sell', trend_low
    # print("No trade found")
    return [], [], type, trend


def check_for_new_high(df, type, trend, all_orders, orders):
    if type == 'buy':
        if all_orders['Entry'] is not None:
            if df.high.iloc[-1] > trend:
                print("New High")
                return reset_orders(symbol)
    if type == 'sell':
        if all_orders['Entry'] is not None:
            if df.low.iloc[-1] < trend:
                print("New Low")
                return reset_orders(symbol)
    return all_orders, orders


def place_stop_loss_order(amount, stop_trigger, orders, side, symbol):
    sl_params = {
        'ordType': 'Stop',
        'triggerType': 'ByLastPrice',
        'stopPxRp': stop_trigger
    }
    try:
        order = exchange.create_order(symbol, 'market', side, amount, stop_trigger, params=sl_params)
        print(f"Stop loss order placed: {order['id']}")
        orders.append(order['id'])
        return orders
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        reset_orders(symbol)
        return []


def place_take_profit_order(amount, take_profit_price, orders, side, symbol):
    tp_params = {
        'ordType': 'LimitIfTouched',
        'triggerType': 'ByLastPrice',
        'stopPxRp': take_profit_price
    }
    try:
        order = exchange.create_order(symbol, 'limit', side, amount, take_profit_price, params=tp_params)
        print(f"Take profit order placed: {order['id']}")
        orders.append(order['id'])
        return orders
    except ccxt.BaseError as e:
        print(f"An error occurred: {str(e)}")
        # exchange.close_position(symbol)
        reset_orders(symbol)
        return []


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
    all_orders = {'Entry': None, 'Limit1': None, 'Limit2': None, 'TakeProfit': None, 'StopLoss': None}
    orders = []
    in_position = False
    return all_orders, orders


def fetch_historical_data(symbol):
    data = exchange.fetch_ohlcv(symbol=symbol, timeframe='5m', limit=1000)
    data15 = exchange.fetch_ohlcv(symbol=symbol, timeframe='15m', limit=1000)
    data1h = exchange.fetch_ohlcv(symbol=symbol, timeframe='1h', limit=1000)
    df = pd.DataFrame(data, columns=['datetime', 'high', 'low', 'open', 'close', 'volume'])
    df15 = pd.DataFrame(data15, columns=['datetime', 'high', 'low', 'open', 'close', 'volume'])
    df1h = pd.DataFrame(data1h, columns=['datetime', 'high', 'low', 'open', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    return df, df15, df1h


def add_EMAs(df):
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['rolling_high'] = df['high'].rolling(window=12 * 36).max()
    df['rolling_low'] = df['low'].rolling(window=12 * 36).min()
    return df

def check_for_entry(orders, all_orders, EP, L1, Entry_size, type, symbol, end_trade, prev_size, log_prices):
    new_orders = orders
    closed_orders = exchange.fetch_closed_orders(symbol)
    for order in closed_orders:
        if order['status'] == 'closed':
            order_id = order['id']
            if order_id == all_orders['Entry']:
                print("Entry Reached")
                end_trade = 'Entry Win'
                all_orders['Entry'] = None
            elif order_id == all_orders['Limit1']:
                exchange.cancel_order(all_orders['TakeProfit'], symbol)
                if type == 'buy':
                    new_orders = place_take_profit_order(Entry_size*4, EP, orders, 'sell', symbol)
                elif type == 'sell':
                    new_orders = place_take_profit_order(Entry_size*4, EP, orders, 'buy', symbol)
                all_orders['TakeProfit'] = new_orders[-1]
                end_trade = 'L1 Win'
                all_orders['Limit1'] = None
            elif order_id == all_orders['Limit2']:
                exchange.cancel_order(all_orders['TakeProfit'], symbol)
                if type == 'buy':
                    new_orders = place_take_profit_order(Entry_size*9, L1, orders, 'sell', symbol)
                elif type == 'sell':
                    new_orders = place_take_profit_order(Entry_size*9, L1, orders, 'buy', symbol)
                all_orders['TakeProfit'] = new_orders[-1]
                end_trade = 'L2 Win'
                all_orders['Limit2'] = None
            elif order_id == all_orders['TakeProfit']:
                log_results(log_prices, prev_size, symbol, end_trade)
                all_orders, new_orders = reset_orders(symbol)
            elif order_id == all_orders['StopLoss']:
                log_results(log_prices, prev_size, symbol, end_trade)
                all_orders, new_orders = reset_orders(symbol)
                end_trade = 'Stop Loss'
    return all_orders, new_orders, end_trade

"""def check_for_entry(orders, all_orders, EP, L1, Entry_size, type, symbol):
    new_orders = orders
    open_orders = exchange.fetch_open_orders(symbol)
    position_size = exchange.fetch_positions([symbol])[0]['info']['size']
    if position_size == 0 and len(open_orders) < 3:
        all_orders, new_orders = reset_orders(all_orders, symbol)
    return all_orders, new_orders"""

def log_results(log_prices, prev_size, symbol, end_trade):
    bal = exchange.fetch_balance()
    accountSize = bal['info']['data']['account']['accountBalanceRv']
    pnl = accountSize - prev_size
    date = dt.datetime.now()
    with open('TCLM_log.txt', 'w') as file:
        file.write(f'{date}   {symbol}   {end_trade}  PnL: ${pnl} EP: {log_prices[0]} L1: {log_prices[1]} L2: {log_prices[2]} TP: {log_prices[3]} SL: {log_prices[4]}')

def check_historical_trades(symbol):
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
        prices, sizes, type, trend = check_for_trades(data, data15, data1h, compound, 20, .1, type, trend)
        # print(prices)
        # print(type)
        if len(prices) > 0:
            stored_prices = prices
            stored_sizes = sizes
            print(stored_prices)
        stored_prices, trade_check = trade_completion_check(stored_prices, trade_check, type,  data)
    return stored_prices, stored_sizes, type, trend


def trade_completion_check(stored_prices, trade_check, type, df):
    if len(stored_prices) > 0:
        EP = stored_prices[0]
        L1 = stored_prices[1]
        L2 = stored_prices[2]
        SL = stored_prices[4]
    if len(stored_prices) > 0 and type == 'buy':
        if trade_check == 0:
            if df['low'].iloc[-1] < L2:
                trade_check = 2
            elif df['low'].iloc[-1] < L1:
                trade_check = 1
        elif trade_check == 1:
            if df['high'].iloc[-1] > EP:
                stored_prices = []
                trade_check = 0
                print("Trade would be completed")
            elif df['low'].iloc[-1] < L2:
                trade_check = 2
        elif trade_check == 2:
            if df['high'].iloc[-1] > L1:
                stored_prices = []
                trade_check = 0
                print("Trade would be completed")
            elif df['low'].iloc[-1] < SL:
                stored_prices = []
                trade_check = 0
                print("Trade would be completed")
    if len(stored_prices) > 0 and type == 'sell':
        if trade_check == 0:
            if df['high'].iloc[-1] > L2:
                trade_check = 2
            elif df['high'].iloc[-1] > L1:
                trade_check = 1
        elif trade_check == 1:
            if df['low'].iloc[-1] < EP:
                stored_prices = []
                trade_check = 0
                print(f"Trade would be completed")
            elif df['high'].iloc[-1] > L2:
                trade_check = 2
        elif trade_check == 2:
            if df['low'].iloc[-1] < L1:
                stored_prices = []
                trade_check = 0
                print("Trade would be completed")
            elif df['high'].iloc[-1] > SL:
                stored_prices = []
                trade_check = 0
                print("Trade would be completed")
    return stored_prices, trade_check

# Error Handling
# Check if there are orders/positions on startup
if __name__ == '__main__':
    # Replace with your API keys
    api_key, secret = getKey()
    exchange = ccxt.phemex({
        'apiKey': api_key,
        'secret': secret,
        'options': {'defaultType': 'swap'}
    })
    compound = False
    Entry = False
    all_orders = {'Entry': None, 'Limit1': None, 'Limit2': None, 'TakeProfit': None, 'StopLoss': None}
    orders = []
    prices = []
    stored_sizes = []
    Entry_size = 0
    TP = 0
    SL = 0
    EP = 0
    L1 = 0
    L2 = 0
    trade_check = 0
    starting_trade = 0
    in_position = False
    log_bal = 0
    log_prices = []
    end_trade = ''
    for symbol in symbols:
        exchange.set_position_mode(hedged=False, symbol=symbol)
        exchange.set_leverage(-50, symbol)
        reset_orders(symbol)
    for i in range(len(symbols)):
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
            break
    while True:
        symbol = symbols_queue.pop()
        df, df15, df1h = fetch_historical_data(symbol)
        df = add_EMAs(df)
        supports, resistances = find_support_resistance(df, 40)
        df = add_support_resistance(df, supports, resistances)
        current_time = dt.datetime.now().time()
        print(symbol)
        print(current_time)
        bal = exchange.fetch_balance()
        accountSize = bal['info']['data']['account']['accountBalanceRv']
        if dt.time(0, 0) <= current_time < dt.time(9, 0):
            if all_orders['Entry'] is not None:
                reset_orders(symbol)
        if len(orders) > 0 and all_orders['Entry'] is not None:
            all_orders, orders = check_for_new_high(df, type, trend, all_orders, orders)
        if len(orders) < 1 and not in_position:
            print(orders)
            prices, sizes, type, trend = check_for_trades(df, df15, df1h, compound, 20, .1, type, trend)
        if len(prices) > 0:
            print(prices)
            Entry_size = sizes[0]
            EP = prices[0]
            L1 = prices[1]
            if dt.time(0, 0) <= current_time < dt.time(9, 0):
                stored_prices = prices
                stored_prices.append(symbol)
                stored_sizes = sizes
                # Check to see if the "would-be" trade played out already
            elif len(orders) < 1:
                print(prices)
                print(sizes)
                orders = place_orders(prices, sizes, type, symbol)
                all_orders['Entry'] = orders[0]
                all_orders['Limit1'] = orders[1]
                all_orders['Limit2'] = orders[2]
                all_orders['TakeProfit'] = orders[3]
                all_orders['StopLoss'] = orders[4]
                log_prices = prices
                log_bal = accountSize
        if len(stored_prices) > 0:
            if symbol == stored_prices[-1]:
                stored_prices, trade_check = trade_completion_check(stored_prices, trade_check, type, df)
                if current_time > dt.time(9, 0):
                    orders = place_orders(stored_prices, stored_sizes, type, symbol)
                    EP = stored_prices[0]
                    L1 = stored_prices[1]
                    Entry_size = stored_sizes[0]
                    all_orders['Entry'] = orders[0]
                    all_orders['Limit1'] = orders[1]
                    all_orders['Limit2'] = orders[2]
                    all_orders['TakeProfit'] = orders[3]
                    all_orders['StopLoss'] = orders[4]
                    stored_prices = []
                    stored_sizes = []
                    log_prices = prices
                    log_bal = accountSize
        if len(orders) > 0:
            all_orders, orders, end_trade = check_for_entry(orders, all_orders, EP, L1, Entry_size, type, symbol, end_trade, log_bal, log_prices)
        if len(orders) > 0:
            symbols_queue.append(symbol)
        else:
            symbols_queue.appendleft(symbol)
        print("waiting 20 seconds")
        time.sleep(20)
