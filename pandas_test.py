import ccxt
import pandas as pd
import pandas_ta as ta

# Initialize the ccxt exchange
exchange = ccxt.phemex()  # Change this to your preferred exchange

# Specify the symbol and timeframe
symbol = 'BTC/USDT'  # Change this to the desired cryptocurrency pair
timeframe = '1d'      # Change this to the desired timeframe (e.g., '1d' for daily data)

# Fetch OHLCV data
ohlcv = exchange.fetch_ohlcv(symbol, timeframe)

# Convert data to DataFrame
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df.set_index('timestamp', inplace=True)

# Calculate EMAs
df['ema_20'] = ta.ema(df['close'], length=20)
df['ema_50'] = ta.ema(df['close'], length=50)
df['ema_200'] = ta.ema(df['close'], length=200)

# Print the DataFrame
print(df)
