# Import everything
import pandas as pd
import backtrader as bt
import numpy as np
import ccxt
import backtrader.feeds as btfeeds
import datetime as dt
import csv
from analyze_strat import load_csv_to_list, sort_data_by_last_element, print_sorted_data


def fetch_historical_data(symbol, start_date, end_date, exchange='phemex'):
    # Example for crypto data using ccxt
    exchange = ccxt.phemex()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=1000)
    data = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data.set_index('timestamp', inplace=True)
    return data


# This function finds support and resistance points of the data given
def find_support_resistance(df, window=4):
    supports = []
    resistances = []
    for i in range(window, len(df) - window):
        if df['low'].iloc[i] == df['low'].iloc[i - window:i + window + 1].min():
            supports.append((df.index[i], df['low'].iloc[i]))
        if df['high'].iloc[i] == df['high'].iloc[i - window:i + window + 1].max():
            resistances.append((df.index[i], df['high'].iloc[i]))
    return supports, resistances


# This function finds fair value gaps of the data provided
def find_fair_value_gaps(df):
    gaps = []
    for i in range(2, len(df)):
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            gaps.append((df.index[i], df['low'].iloc[i], df['high'].iloc[i - 2], df['low'].iloc[i]-df['high'].iloc[i - 2], 'bullish'))
        elif df['low'].iloc[i-2] > df['high'].iloc[i]:
            gaps.append((df.index[i], df['low'].iloc[i-2], df['high'].iloc[i], df['low'].iloc[i-2]-df['high'].iloc[i], 'bearish'))
    return gaps


class TCLMax(bt.Strategy):
    params = (
        ('ema_check_param', False),
        ('rolling_period', 36),
        ('too_steep', 0.055),
        ('steep_candles', 16),
        ('min_range', 0.04),
        ('max_range', 0.09),
        ('established_low', 40),
        ('data_name', ''),
    )
    # __init__ initializes all the variables to be used in the strategy when the strategy is loaded
    def __init__(self):
        # Initialize all the values for the strategy
        # 5m, 15m, 1hr, 4hr 200 EMA, 5m 20 EMA, 50 EMA
        self.ema20 = bt.ind.EMA(period=20)
        self.ema50 = bt.ind.EMA(period=50)
        self.ema200 = bt.ind.EMA(period=200)
        self.ema15m = bt.ind.EMA(period=600)
        self.ema1hr = bt.ind.EMA(period=2400)
        # Define S/R
        self.rolling_high = bt.indicators.Highest(self.data.open, period=12*self.params.rolling_period)
        self.rolling_low = bt.indicators.Lowest(self.data.high, period=12*self.params.rolling_period)
        # High, Low, Range, Fib Levels: 1, 0, 0.618, 1.272, 0.382, 0.17, -0.05
        self.trend_low = 0
        self.trend_high = 0
        self.EP = 0
        self.L1 = 0
        self.L2 = 0
        self.SL = 0
        self.TP = 0
        # Initialize order sizes
        self.Entry_size = 0
        self.Limit1_size = 0
        self.Limit2_size = 0
        # Initialize orders
        self.Entry = None
        self.Limit1 = None
        self.Limit2 = None
        self.StopLoss = None
        self.TakeProfit = None
        # Initialize account size and leverage
        self.accountSize = 1000
        self.leverage = 50
        # Initialize the rest of the variables
        self.order_list = []
        self.ready_for_entry = 0
        self.trade_check = 0
        self.dir = 1
        self.stored_trade = None
        self.risk = 0.35
        self.compound = 1
        self.too_steep = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.L1_hit = 0
        self.L2_hit = 0
        self.SL_hit = 0
        self.count = 0
    # notify_trade is called whenever changes are made to the trade
    def notify_trade(self, trade):
        # check if the trade has been closed and print results
        if trade.isclosed:
            # print(f"TRADE closed, Profit: {trade.pnl}, Net Profit: {trade.pnlcomm}")
            current_position_size = self.position.size
            # print(f"Current position size: {current_position_size}")
            # Make sure no order got double triggered
            if current_position_size > 0:
                self.sell()
            elif current_position_size < 0:
                self.buy()
            # Clear and reset orders
            self.accountSize += trade.pnl
            # print(self.accountSize)
            self.cancel_all_orders()
            self.StopLoss = None
            self.TakeProfit = None
            self.Entry = None
            self.Limit1 = None
            self.Limit2 = None
            self.order_list = []
    # This function cancels all open orders
    def cancel_all_orders(self):
        # Cancel all open orders
        for order in self.broker.get_orders_open():
            self.cancel(order)
        self.order_list.clear()
    # This sets all orders to None
    def clear_order_references(self):
        self.StopLoss = None
        self.TakeProfit = None
        self.Entry = None
        self.Limit1 = None
        self.Limit2 = None
    # notify_order is triggered whenever a change to an order has been made
    def notify_order(self, order):
        # LONG
        if self.dir == 1:
            # Check if the order was completed
            if order.status in [order.Completed]:
                # print(f"Order Complete")
                if order == self.TakeProfit:
                    # print(f"TAKE PROFIT LONG order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                    self.cancel_all_orders()
                    self.winning_trades += 1
                    self.total_trades += 1
                elif order == self.StopLoss:
                    # print(f"STOP LOSS LONG order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                    # print(self.SL)
                    self.SL_hit += 1
                    self.total_trades += 1
                    # for orders in self.broker.get_orders_open():
                        # print(orders)
                    self.cancel_all_orders()
                    # for orders in self.broker.get_orders_open():
                        # print(orders)
                else:
                    # print(f"BUY order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                    if not self.TakeProfit:
                        # Place take profit
                        self.TakeProfit = self.sell(price=self.TP, exectype=bt.Order.Limit, size=None)
                        # print("TP placed")
                    else:
                        if order == self.Limit1:
                            # update take profit
                            self.TakeProfit = self.sell(exectype=bt.Order.Limit, price=self.EP, size=None)
                            self.L1_hit += 1
                            # print("TP updated L1")
                        if order == self.Limit2:
                            # update take profit
                            self.cancel(self.TakeProfit)
                            self.TakeProfit = self.sell(exectype=bt.Order.Limit, price=self.L1, size=None)
                            self.L2_hit += 1
                            # print("TP updated L2")
                            if not self.StopLoss:
                                # place stop loss
                                self.StopLoss = self.sell(price=self.SL, exectype=bt.Order.StopLimit, plimit=self.SL, size=None)
                                # print("Stop Loss placed")
                # Set the entry to None
                self.Entry = None
            # elif order.status in [order.Canceled]:
                # print("Order Canceled")
            # elif order.status in [order.Margin, order.Rejected]:
                # print('Order Margin/Rejected')
        # SHORT
        elif self.dir == 0:
            # Check if order was completed
            if order.status in [order.Completed]:
                # print(f"Order Complete")
                if order == self.TakeProfit:
                    # print(f"TAKE PROFIT SHORT order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                    self.cancel_all_orders()
                    self.total_trades += 1
                    self.winning_trades += 1
                elif order == self.StopLoss:
                    # print(f"STOP LOSS SHORT order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                    self.SL_hit += 1
                    self.total_trades += 1
                    # for orders in self.broker.get_orders_open():
                        # print(orders)
                    self.cancel_all_orders()
                    # for orders in self.broker.get_orders_open():
                        # print(orders)
                else:
                    # print(f"SELL order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                    if not self.TakeProfit:
                        # Place take profit
                        self.TakeProfit = self.buy(price=self.TP, exectype=bt.Order.Limit, size=None)
                        # print("TP placed")
                    else:
                        if order == self.Limit1:
                            # Update take profit to L1
                            self.TakeProfit = self.buy(exectype=bt.Order.Limit, price=self.EP, size=None)
                            self.L1_hit += 1
                            # print("TP updated L1")
                        if order == self.Limit2:
                            # Update take profit to L2
                            self.cancel(self.TakeProfit)
                            self.TakeProfit = self.buy(exectype=bt.Order.Limit, price=self.L1, size=None)
                            self.L2_hit += 1
                            # print("TP updated L2")
                            if not self.StopLoss:
                                # Place stop loss
                                self.StopLoss = self.buy(price=self.SL, exectype=bt.Order.StopLimit, plimit=self.SL, size=None)
                                # print("Stop Loss placed")
                # Reset Entry
                self.Entry = None
            # elif order.status in [order.Canceled]:
                # print("Order Canceled")
            # elif order.status in [order.Margin, order.Rejected]:
                # print('Order Margin/Rejected')
    # This is the main function of the strategy. Next gets called with each line of data (or candle). It checks if the
    # trade conditions are met, and if so, it places the orders.
    def next(self):
        if not self.position:  # Check if we are not in the market
            current_time = self.data.datetime.time(0)  # Get the time
            # Do not trade during 0:00 and 9:00 for the London and NY stock exchange open
            if dt.time(0, 0) <= current_time < dt.time(9, 0):
                # Cancel orders if they already are in place
                if self.Entry:
                    self.cancel_all_orders()
                    self.clear_order_references()
                # Check to see if the "would-be" trade played out already
                if self.stored_trade and self.dir == 1:
                    if self.trade_check == 0:
                        if self.data.low[0] < self.L2:
                            self.trade_check = 2
                        elif self.data.low[0] < self.L1:
                            self.trade_check = 1
                    elif self.trade_check == 1:
                        if self.data.high[0] > self.EP:
                            self.stored_trade = None
                            self.trade_check = 0
                        elif self.data.low[0] < self.L2:
                            self.trade_check = 2
                    elif self.trade_check == 2:
                        if self.data.high[0] > self.L1:
                            self.stored_trade = 0
                            self.trade_check = 0
                        elif self.data.low[0] < self.SL:
                            self.stored_trade = None
                            self.trade_check = 0
                # Do the same thing for a short
                if self.stored_trade and self.dir == 0:
                    if self.trade_check == 0:
                        if self.data.high[0] > self.L2:
                            self.trade_check = 2
                        elif self.data.high[0] > self.L1:
                            self.trade_check = 1
                    elif self.trade_check == 1:
                        if self.data.low[0] > self.EP:
                            self.stored_trade = None
                            self.trade_check = 0
                        elif self.data.high[0] > self.L2:
                            self.trade_check = 2
                    elif self.trade_check == 2:
                        if self.data.low[0] < self.L1:
                            self.stored_trade = None
                            self.trade_check = 0
                        elif self.data.high[0] > self.SL:
                            self.stored_trade = None
                            self.trade_check = 0
            # If a trade would have been placed during the time range, check to make sure a new higher high has not been
            # made
            if self.stored_trade:
                if self.dir == 1:
                    if self.data.high[0] > self.trend_high:
                        self.trend_high = self.data.high[0]
                        self.stored_trade = None
                elif self.dir == 0:
                    if self.data.low[0] < self.trend_low:
                        self.trend_low = self.data.low[0]
                        self.stored_trade = None
            # If an order has been placed, check to see if a new HH/LL has been made
            # If so, cancel the orders
            if self.Entry:
                if self.dir == 1:
                    if self.data.high[0] > self.trend_high:
                        self.trend_high = self.data.high[0]
                        self.cancel_all_orders()
                        self.clear_order_references()
                elif self.dir == 0:
                    if self.data.low[0] < self.trend_low:
                        self.trend_low = self.data.low[0]
                        self.cancel_all_orders()
                        self.clear_order_references()
            # To enter:
            # 1. New 48hr high
            # 2. 20, 50, 200 EMAs lined up
            # 3. Price above 200 EMA on 5m, 15m, 1hr
            # 4. Established low 12-36hrs previous
            # 5. Range 4-7%
            # 6. No 1hr FVG right below SL
            # 7. Retrace to 0.618
            # If ready to enter, place the orders
            # LONG
            # Check if the low is actually the lowest low in the range
            # Test different ranges
            # Make sure there has not been a sharp increase in price
            # Check for 1 hr FVGs
            # 1. 20, 50, 200 EMAs lined up
            elif self.data.open[0] == self.rolling_high:
                # 2. Price above 200 EMA on 5m, 15m, 1hr
                if self.data.open[0] > self.ema15m and self.data.open[0] > self.ema1hr:
                    # 3. New 48hr high
                    if self.ema20 > self.ema50 > self.ema200 or self.params.ema_check_param:
                        self.trend_high = self.data.open[0]
                        # 4. Established low 12-36hrs previous
                        for i in range(-432, -144):
                            window_low = self.data.high.get(size=self.params.established_low * 2 + 1, ago=i+self.params.established_low)
                            window_low2 = self.data.high.get(size=-i+10, ago=-1)
                            if self.data.high[i] == min(window_low) and self.data.high[i] == min(window_low2):
                                # 5. Range 4-7%
                                self.too_steep = 0
                                for j in range(-600, -self.params.steep_candles):
                                    if (self.data.open[j + self.params.steep_candles] - self.data.high[j])/self.data.high[j] > self.params.too_steep:
                                        self.too_steep = 1
                                if self.too_steep == 0:
                                    if self.params.min_range < (self.trend_high-self.data.high[i])/self.data.high[i] < self.params.max_range:
                                        self.trend_low = self.data.high[i]
                                        self.EP = (self.trend_high-self.trend_low)*0.618+self.trend_low
                                        self.L1 = (self.trend_high-self.trend_low)*0.382+self.trend_low
                                        self.L2 = (self.trend_high-self.trend_low)*0.17+self.trend_low
                                        self.SL = -(self.trend_high-self.trend_low)*0.05+self.trend_low
                                        self.TP = (self.trend_high-self.trend_low)*1.272+self.trend_low
                                        # print(f"E: {self.EP}, TP: {self.TP}, L1: {self.L1}, L2: {self.L2}, SL: {self.SL}, High: {self.trend_high}, Low: {self.trend_low}")
                                        # Calculate Entry, L1, and L2 position size so L1 avg cost is at 0.441 and L2 at 0.29
                                        # 35% Account risk on 50x leverage
                                        if self.compound:
                                            self.Entry_size = (self.accountSize * self.risk)/(self.EP + 3 * self.L1 + 5 * self.L2 - 9 * self.SL)
                                        else:
                                            self.Entry_size = (350)/(self.EP + 3 * self.L1 + 5 * self.L2 - 9 * self.SL)
                                        self.Limit1_size = 3*self.Entry_size
                                        self.Limit2_size = 5*self.Entry_size
                                        # Check to see if we are in the time range. If so, store the order instead of placing it
                                        if (dt.time(0, 0) <= current_time and current_time < dt.time(9, 0)):
                                            self.stored_trade = ('buy', self.EP, self.Entry_size, self.L1, self.Limit1_size, self.L2, self.Limit2_size, self.TP, self.SL)
                                            # print("Long trade setup stored")
                                        else:
                                            self.Entry = self.buy(exectype=bt.Order.Limit, price=self.EP, size=self.Entry_size)
                                            self.Limit1 = self.buy(exectype=bt.Order.Limit, price=self.L1, size=self.Limit1_size)
                                            self.Limit2 = self.buy(exectype=bt.Order.Limit, price=self.L2, size=self.Limit2_size)
                                            # print("Long Order placed")
                                        self.dir = 1
                                        self.trade_check = 0
                                        break
            # SHORT
            # 1. Check to see if the EMAs are aligned
            elif self.data.high[0] == self.rolling_low:
                # 2. Price below 200 EMA on 5m, 15m, 1hr
                if self.data.high[0] < self.ema15m and self.data.high[0] < self.ema1hr:
                    # 3. New 48hr low
                    if self.ema20 < self.ema50 < self.ema200 or self.params.ema_check_param:
                        self.trend_low = self.data.high[0]
                        # 4. Established high 12-36hrs previous
                        for i in range(-432, -144):
                            window_high = self.data.open.get(size=self.params.established_low * 2 + 1, ago=i+self.params.established_low)
                            window_high2 = self.data.open.get(size=-i+10, ago=-1)
                            if self.data.open[i] == max(window_high) and self.data.open[i] == max(window_high2):
                                # 5. Range 4-7%
                                self.too_steep = 0
                                for j in range(-600, -self.params.steep_candles):
                                    if (self.data.open[j] - self.data.high[j+self.params.steep_candles])/self.data.open[j] > self.params.too_steep:
                                        self.too_steep = 1
                                if self.too_steep == 0:
                                    if self.params.min_range < (self.data.open[i]-self.trend_low)/self.data.open[i] < self.params.max_range:
                                        self.trend_high = self.data.open[i]
                                        self.EP = (self.trend_low-self.trend_high)*0.618+self.trend_high
                                        self.L1 = (self.trend_low-self.trend_high)*0.382+self.trend_high
                                        self.L2 = (self.trend_low-self.trend_high)*0.17+self.trend_high
                                        self.SL = -(self.trend_low-self.trend_high)*0.05+self.trend_high
                                        self.TP = (self.trend_low-self.trend_high)*1.272+self.trend_high
                                        # print(f"E: {self.EP}, TP: {self.TP}, L1: {self.L1}, L2: {self.L2}, SL: {self.SL}, High: {self.trend_high}, Low: {self.trend_low}")
                                        # Calculate Entry, L1, and L2 position size so L1 avg cost is at 0.441 and L2 at 0.29
                                        # 35% Account risk on 50x leverage
                                        if self.compound:
                                            self.Entry_size = abs((self.accountSize * self.risk)/(self.EP + 3 * self.L1 + 5 * self.L2 - 9 * self.SL))
                                        else:
                                            self.Entry_size = abs(350/(self.EP + 3 * self.L1 + 5 * self.L2 - 9 * self.SL))
                                        self.Limit1_size = 3*self.Entry_size
                                        self.Limit2_size = 5*self.Entry_size
                                        # Check to see if we are in the time range. If so, store the order instead of placing it
                                        if dt.time(0, 0) <= current_time < dt.time(
                                                9, 0):
                                            self.stored_trade = (
                                            'sell', self.EP, self.Entry_size, self.L1, self.Limit1_size, self.L2,
                                            self.Limit2_size, self.TP, self.SL)
                                            # print(f"Short trade setup stored Time: {current_time}")
                                        else:
                                            self.Entry = self.sell(exectype=bt.Order.Limit, price=self.EP, size=self.Entry_size)
                                            self.Limit1 = self.sell(exectype=bt.Order.Limit, price=self.L1, size=self.Limit1_size)
                                            self.Limit2 = self.sell(exectype=bt.Order.Limit, price=self.L2, size=self.Limit2_size)
                                            # print("Short Order placed")
                                        self.dir = 0
                                        self.trade_check = 0
                                        break
            # Once we exit NY open, check if we can place orders for a late entry trade
            if self.stored_trade and dt.time(9, 0) <= current_time:
                trade_type, EP, Entry_size, L1, Limit1_size, L2, Limit2_size, self.TP, self.SL = self.stored_trade
                # print(
                #     f"Trade Type: {trade_type}, E: {self.EP}, TP: {self.TP}, L1: {self.L1}, L2: {self.L2}, SL: {self.SL}, High: {self.trend_high}, Low: {self.trend_low}")
                if trade_type == 'buy':
                    if self.data.low[0] < self.SL:
                        self.stored_trade = None
                        return
                    self.Entry = self.buy(exectype=bt.Order.Limit, price=EP, size=Entry_size)
                    self.Limit1 = self.buy(exectype=bt.Order.Limit, price=L1, size=Limit1_size)
                    self.Limit2 = self.buy(exectype=bt.Order.Limit, price=L2, size=Limit2_size)
                    # print("Stored Long Order placed")
                    self.dir = 1
                elif trade_type == 'sell':
                    if self.data.high[0] > self.SL:
                        self.stored_trade = None
                        return
                    self.Entry = self.sell(exectype=bt.Order.Limit, price=EP, size=Entry_size)
                    self.Limit1 = self.sell(exectype=bt.Order.Limit, price=L1, size=Limit1_size)
                    self.Limit2 = self.sell(exectype=bt.Order.Limit, price=L2, size=Limit2_size)
                    # print("Stored Short Order placed")
                    self.dir = 0
                self.stored_trade = None

    def stop(self):
        win_percentage = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        print(f'Total Trades: {self.total_trades}')
        print(f'Winning Trades: {self.winning_trades}')
        print(f'Winning Percentage: {win_percentage:.2f}%')
        Losing_trades = self.total_trades - self.winning_trades
        L2_wins = self.L2_hit - Losing_trades
        L1_wins = self.L1_hit - self.L2_hit
        Entry_wins = self.total_trades - self.L1_hit
        final_value = self.broker.getvalue()
        profit = 250 * 1.1**Entry_wins * 1.1**L1_wins * 1.12**L2_wins * 0.5**Losing_trades - 250
        print(f"Entry wins: {Entry_wins}, L1 wins: {L1_wins}, L2 wins: {L2_wins}, Losses: {Losing_trades}, Profit: {profit}")
        with open('hlocTCLM_strategy_results.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([self.params.data_name, self.params.rolling_period,self.params.too_steep,self.params.steep_candles,self.params.min_range,self.params.max_range,
                            self.params.established_low,self.params.ema_check_param, self.total_trades, self.winning_trades, Losing_trades, L1_wins, L2_wins, Entry_wins,
                             win_percentage, profit])

if __name__ == '__main__':
    # Create variable
    exchange = 'phemex'
    coin = 'BTC/USDT'
    cash = 10000000.0
    risk = 5

    # initialize Cerebro and get data
    """df = pd.read_csv("matic_usd_5min_data.csv", parse_dates=['datetime'])
    df = pd.DataFrame(df)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.drop(columns=['milliseconds'], inplace=True)
    df.set_index('datetime', inplace=True)"""
    """df['RollingHigh'] = df['high'].rolling(window=(12*48)).max()
    df = df.fillna(0)"""
    # df15 = pd.read_csv("15m_test_data.csv", parse_dates=['datetime'])
    # df['datetime'] = pd.to_datetime(df['datetime'])
    # df1 = pd.read_csv("1h_test_data.csv", parse_dates=['datetime'])
    # df['datetime'] = pd.to_datetime(df['datetime'])
    # supports, resistances = find_support_resistance(df, 52)
    # hr_supports, hr_resistances = find_support_resistance(df1)
    """df['Support'] = 0
    df['Resistance'] = 0
    for group in supports:
        df.loc[group[0], 'Support'] = 1
    for group in resistances:
        df.loc[group[0], 'Resistance'] = 1"""
    # gaps = find_fair_value_gaps(df)
    # hr_gaps = find_fair_value_gaps(df1)
    # print(gaps)
    # print(hr_gaps)
    # print(supports)
    # print(hr_supports)
    # print(resistances)
    # print(hr_resistances)
    # print(df)
    # print(df15)
    # print(df1)
    data_files = ['data_5min/matic_usd_5min_data4.csv', 'data_5min/dot_usd_5min_data4.csv', 'data_5min/link_usd_5min_data4.csv', 'data_5min/ada_usd_5min_data4.csv', 'data_5min/atom_usd_5min_data4.csv',
                  'data_5min/sol_usd_5min_data4.csv', 'data_5min/xrp_usd_5min_data4.csv', 'data_5min/apt_usd_5min_data2.csv']
    cerebro = bt.Cerebro()
    # Load the data
    for data_file in data_files:
        data = btfeeds.GenericCSVData(
            dataname=data_file,

            nullvalue=0.0,
            compression=5,
            timeframe=bt.TimeFrame.Minutes,
            datetime=0,
            open=1,
            high=2,
            low=3,
            close=4,
            volume=5,
            openinterest=-1
        )
        cerebro = bt.Cerebro()
        cerebro.adddata(data)
        cerebro.optstrategy(
            TCLMax,
            ema_check_param=[False, True],
            rolling_period=[24, 36, 48],
            too_steep=[0.05, 0.07],
            steep_candles=[15],
            min_range=[0.03, 0.04],
            max_range=[0.06, 0.08, 0.1],
            established_low=[30, 40, 52, 64],
            data_name=[data_file],
        )
        # cerebro.addstrategy(TCLMax)
        cerebro.broker.setcash(cash)
        cerebro.broker.set_slippage_perc(0.005)
        cerebro.broker.setcommission(commission=0.0000)
        cerebro.addsizer(bt.sizers.PercentSizer, percents=risk)
        cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="areturn")
        teststrat = cerebro.run(maxcpus=8)
        # cerebro.plot()
    # print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # print(teststrat[0].analyzers.areturn.get_analysis())

    filename = 'new_TCLM_strategy_results.csv'
    data = load_csv_to_list(filename)

    # Sort data by the last element (win percentage)
    sorted_data = sort_data_by_last_element(data)

    # Print sorted data
    print("Sorted Strategy Results (by Winning Percentage):")
    print_sorted_data(sorted_data)
