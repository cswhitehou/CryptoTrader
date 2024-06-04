import pandas as pd


def find_support_resistance(df, window=4):
    supports = []
    resistances = []
    for i in range(window, len(df) - window):
        if df['low'].iloc[i] == df['low'].iloc[i - window:i + window + 1].min():
            supports.append((df.index[i], df['low'].iloc[i]))
        if df['high'].iloc[i] == df['high'].iloc[i - window:i + window + 1].max():
            resistances.append((df.index[i], df['high'].iloc[i]))
    return supports, resistances

# Read the CSV data into a DataFrame
df = pd.read_csv('matic_usd_5min_data.csv')

# Drop the 'milliseconds' column if it's not needed
# df = df.drop(columns=['milliseconds'])
# df = df.drop(columns=['adj_close'])
df = df.drop(columns=['RollingHigh'])
df = df.drop(columns=['Support'])
df = df.drop(columns=['Resistance'])
# Ensure the datetime column is correctly parsed as datetime objects


# Set the datetime column as the index
df.set_index('datetime', inplace=True)

# Ensure the data types are correct
# Save the cleaned data to a new CSV file
df.to_csv('matic_usd_5min_data.csv')
print(df)
