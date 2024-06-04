import ccxt
import pandas_ta as ta
import pandas as pd

symbol = 'ETHUSD'
pos_size = 10
params = {'timeInForce': 'PostOnly', }
target = 5
max_loss = -5
vol_decimal = .4
timeframe = '5m'
exchange = ccxt.phemex()


def ask_bid(symbol=symbol):
    ob = exchange.fetch_order_book(symbol)
    print(ob)

    bid = ob['bids'][0][0]
    ask = ob['asks'][0][0]

    print(f'this is the ask for {symbol} {ask}')

    return ask, bid


def fetch_data(exchange=exchange, symbol=symbol, timeframe=timeframe):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe)

    # Convert data to DataFrame
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)

    return df


data = fetch_data()


def calc_emas(df=data):
    # Calculate EMAs
    df['ema_20'] = ta.ema(df['close'], length=20)
    df['ema_50'] = ta.ema(df['close'], length=50)
    df['ema_200'] = ta.ema(df['close'], length=200)
    return df

