# Import everything
import pandas as pd
import backtrader as bt
import numpy as np
import ccxt
import csv
import os
import backtrader.feeds as btfeeds
from datetime import datetime, timedelta
from analyze_strat import load_csv_to_list, sort_data_by_last_element, print_sorted_data

end_results = []
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


class TC1(bt.Strategy):
    params = (
        ('small_sr_param', 3),
        ('sr_window_param', -12),
        ('sr_req_param', 3),
        ('min_size_param', 0.015),
        ('max_size_param', 0.08),
        ('prev_low_range_param', 72),
        ('low_candles_param', 10),
        ('sr_range_param', 0.0008),
        ('fvg_range_param', 0.001),
        ('ema_check_param', True),
        ('ema_200_param', True),
    )
    global end_results
    # __init__ initializes all the variables to be used in the strategy when the strategy is loaded
    def __init__(self):
        # Initialize all the values
        self.ema20 = bt.ind.EMA(period=20)
        self.ema50 = bt.ind.EMA(period=50)
        self.ema200 = bt.ind.EMA(period=200)
        self.rolling_high = bt.indicators.Highest(self.data.high, period=12*4)
        self.rolling_low = bt.indicators.Lowest(self.data.low, period=12*4)
        self.trend_low = 0
        self.first_high = 0
        self.higher_low = 0
        self.trend_high = 0
        self.last_resistance = 0
        self.supports = []
        self.resistances = []
        self.SR = []
        self.FVGs = []
        self.EP = 0
        self.SL = 0
        self.TP = 0
        self.Entry_size = 0
        self.dir = 1
        self.StopLoss = None
        self.TakeProfit = None
        self.Entry = None
        self.accountSize = 1000
        self.data1h = []
        self.sr_count = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.prev_rsi = 0
        self.sr_window = self.params.sr_window_param
        self.sr_req = self.params.sr_req_param
        self.min_size = self.params.min_size_param
        self.max_size = self.params.max_size_param
        self.prev_low_range = self.params.prev_low_range_param
        self.low_candles = self.params.low_candles_param
        self.sr_range = self.params.sr_range_param
        self.fvg_range = self.params.fvg_range_param
        self.small_sr = self.params.small_sr_param
        self.ema_check = self.params.ema_check_param
        self.ema_200_check = self.params.ema_200_param

    def cancel_all_orders(self):
        # Cancel all open orders
        for order in self.broker.get_orders_open():
            self.cancel(order)

    def clear_order_references(self):
        self.StopLoss = None
        self.TakeProfit = None
        self.Entry = None

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
            self.total_trades += 1
            if trade.pnl > 0:
                self.winning_trades += 1
            self.accountSize+=trade.pnl
            # Clear and reset orders
            self.cancel_all_orders()
            self.clear_order_references()

    def notify_order(self, order):
        if order.status in [order.Completed]:
            # print(f"Order executed, Price: {order.executed.price}, Size: {order.executed.size}")
            if order == self.Entry and self.dir == 1:
                # print(f"BUY LONG order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                if not self.TakeProfit:
                    self.TakeProfit = self.sell(exectype=bt.Order.Limit, price=self.TP, size=order.executed.size)
                    # print("TP LONG placed")
                if not self.StopLoss:
                    self.StopLoss = self.sell(exectype=bt.Order.StopLimit, price=self.SL, plimit=self.SL, size=order.executed.size)
                    # print("SL LONG Placed")
            if order == self.Entry and self.dir == 0:
                # print(f"BUY SHORT order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                if not self.TakeProfit:
                    self.TakeProfit = self.buy(exectype=bt.Order.Limit, price=self.TP, size=order.executed.size)
                    # print("TP SHORT placed")
                if not self.StopLoss:
                    self.StopLoss = self.buy(exectype=bt.Order.StopLimit, price=self.SL, plimit=self.SL, size=order.executed.size)
                    # print("SL SHORT Placed")
            if order == self.StopLoss:
                # print(f"STOP LOSS order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                current_position_size = self.position.size
                # print(f"Current position size: {current_position_size}")
                self.cancel_all_orders()
                self.clear_order_references()
            if order == self.TakeProfit:
                # print(f"TAKE PROFIT order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                current_position_size = self.position.size
                # print(f"Current position size: {current_position_size}")
                self.cancel_all_orders()
                self.clear_order_references()
        # if order.status in [order.Canceled]:
            # print("Order Canceled")

    def get_fair_value_gaps(self):
        if self.data1h[-1][1] > self.data1h[-3][2]:
            fvg = (self.data1h[-1][0], self.data1h[-3][2], self.data1h[-1][1], (self.data1h[-1][1]+self.data1h[-3][2])/2, 'bullish', (self.data1h[-1][1]-self.data1h[-3][2])/self.data1h[-3][2])
            if fvg not in self.FVGs:
                self.FVGs.append(fvg)
                # print("FVG appended")
                # print(fvg)
        elif self.data1h[-1][2] < self.data1h[-3][1]:
            fvg = (self.data1h[-1][0], self.data1h[-1][2], self.data1h[-3][1], (self.data1h[-3][1]+self.data1h[-1][2])/2, 'bearish', (self.data1h[-3][1]-self.data1h[-1][2])/self.data1h[-3][1])
            if fvg not in self.FVGs:
                self.FVGs.append(fvg)
                # print("FVG appended")
                # print(fvg)
        """for fvg in self.FVGs:
            if self.data.high[0] > fvg[2] and fvg[4] == 'bearish':
                self.FVGs.remove(fvg)
                print(f'{fvg} filled')
            elif self.data.low[0] < fvg[2] and fvg[4] == 'bullish':
                self.FVGs.remove(fvg)
                print(f'{fvg} filled')"""
        current_date = self.data.datetime.datetime(0)  # Get the current date from the data feed
        lookback_date = current_date - timedelta(days=3)
        for date in self.FVGs:
            if lookback_date > date[0]:
                self.FVGs.remove(date)
                # print(f'{date} removed from S/R')

    def get_support_resistance(self):
        window_size = -12
        window_low = min(self.data.low.get(size=(-window_size*2)))
        window_high = max(self.data.high.get(size=(-window_size*2)))
        if self.data.high[window_size] == window_high:
            self.SR.append((self.data.datetime.datetime(window_size), self.data.high[window_size], "resistance"))
        if self.data.low[window_size] == window_low:
            self.SR.append((self.data.datetime.datetime(window_size), self.data.low[window_size], "support"))

        current_date = self.data.datetime.datetime(0)  # Get the current date from the data feed
        lookback_date = current_date - timedelta(days=12)
        self.SR = [sr for sr in self.SR if lookback_date < sr[0] <= current_date]

    def next(self):
        if self.data.datetime.datetime(0).minute == 0:
            low_1h = self.data.low.get(size=12, ago=-1)
            high_1h = self.data.high.get(size=12, ago=-1)
            self.data1h.append((self.data.datetime.datetime(0), min(low_1h), max(high_1h)))
        if len(self.data1h) > 3:
            self.get_fair_value_gaps()
        self.get_support_resistance()
        if not self.position:
            current_time = self.data.datetime.time(0)  # Get the time
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
            # 1. 20, 50, 200 EMAs lined up
            # 2. High and a HH
            # 3. Low and a HL
            # 4. At least 2 major S/R points near Entry
            # 5. 200 EMA above SL
            # 6. 1hr FVG around Entry
            # LONG
            # 1. 20, 50, 200 EMAs lined up
            elif (self.ema20 > self.ema50 > self.ema200 or self.ema_check) and self.data.high[0] == self.rolling_high:
                self.trend_high = self.data.high[0]
                # Find most recent support for the low
                for i in range(6, self.prev_low_range):
                    window_low = self.data.low.get(size=self.low_candles, ago=-i)
                    if self.data.low[-i] == min(window_low):
                        self.trend_low = self.data.low[-i]
                        self.prev_rsi = self.rsi[-i]
                        # if not (self.rsi > self.prev_rsi > 70):
                        if self.min_size < (self.trend_high - self.trend_low) / self.trend_low < self.max_size:
                            self.EP = (self.trend_high - self.trend_low) * 0.382 + self.trend_low
                            self.SL = (self.trend_high - self.trend_low) * 0.17 + self.trend_low
                            self.TP = (self.trend_high - self.trend_low) * 1.272 + self.trend_low
                            self.sr_count = 0
                            for j in range(3, i):
                                window_small_low = min(self.data.low.get(size=self.small_sr*2+1, ago=-j+self.small_sr))
                                window_small_high = max(self.data.high.get(size=self.small_sr*2+1, ago=-j+self.small_sr))
                                if self.EP * (1+self.sr_range) > self.data.low[-j] > self.EP * (1-self.sr_range) and self.data.low[-j] == window_small_low:
                                    self.sr_count += 1
                                if self.EP * (1+self.sr_range) > self.data.high[-j] > self.EP * (1-self.sr_range) and self.data.high[-j] == window_small_high:
                                    self.sr_count += 1
                            # print(self.SR)
                            for sr in self.SR:
                                if self.EP * (1+self.fvg_range) > sr[1] > self.EP * (1-self.fvg_range):
                                    self.sr_count += 1
                            if self.sr_count >= self.sr_req and (self.ema200 > self.SL or self.ema_200_check):
                                for fvg in self.FVGs:
                                    if self.SL < fvg[3] < self.EP:
                                        # print(f"E: {self.EP}, TP: {self.TP}, SL: {self.SL}, High: {self.trend_high}, Low: {self.trend_low}")
                                        # Calculate Entry, L1, and L2 position size so L1 avg cost is at 0.441 and L2 at 0.29
                                        # 35% Account risk on 50x leverage
                                        self.Entry_size = 25/(self.EP-self.SL)
                                        # Check to see if we are in the time range. If so, store the order instead of placing it
                                        # if (dt.time(0, 0) <= current_time and current_time < dt.time(9, 0)):
                                            # self.stored_trade = (
                                            # 'buy', self.EP, self.Entry_size, self.TP, self.SL)
                                            # print("Long trade setup stored")
                                        # else:
                                            # self.Entry = self.buy(exectype=bt.Order.Limit, price=self.EP,
                                            #                       size=self.Entry_size)
                                            # print("Long Order placed")
                                        self.Entry = self.buy(exectype=bt.Order.Limit, price=self.EP, size=self.Entry_size)
                                        self.dir = 1
                                        return
            elif (self.ema20 < self.ema50 < self.ema200 or self.ema_check) and self.data.low[0] == self.rolling_low:
                self.trend_low = self.data.low[0]
                # Find most recent support for the low
                for i in range(6, self.prev_low_range):
                    window_high = self.data.high.get(size=self.low_candles, ago=-i)
                    if self.data.high[-i] == max(window_high):
                        self.trend_high = self.data.high[-i]
                        self.prev_rsi = self.rsi[-i]
                        # if not (self.rsi < self.prev_rsi < 70):
                        if self.min_size < (self.trend_high - self.trend_low) / self.trend_high < self.max_size:
                            self.EP = (self.trend_low-self.trend_high) * 0.382 + self.trend_high
                            self.SL = (self.trend_low - self.trend_high) * 0.17 + self.trend_high
                            self.TP = (self.trend_low - self.trend_high) * 1.272 + self.trend_high
                            self.sr_count = 0
                            for j in range(3, i):
                                window_small_low = min(self.data.low.get(size=self.small_sr*2+1, ago=-j+self.small_sr))
                                window_small_high = max(self.data.high.get(size=self.small_sr*2+1, ago=-j+self.small_sr))
                                if self.EP * (1+self.sr_range) > self.data.low[-j] > self.EP * (1-self.sr_range) and self.data.low[-j] == window_small_low:
                                    self.sr_count += 1
                                if self.EP * (1+self.sr_range) > self.data.high[-j] > self.EP * (1-self.sr_range) and self.data.high[-j] == window_small_high:
                                    self.sr_count += 1
                            # print(self.SR)
                            for sr in self.SR:
                                if self.EP * (1+self.fvg_range) > sr[1] > self.EP * (1-self.fvg_range):
                                    self.sr_count += 1
                            if self.sr_count >= self.sr_req and (self.ema200 < self.SL or self.ema_200_check):
                                for fvg in self.FVGs:
                                    if self.SL < fvg[3] < self.EP:
                                        # print(f"E: {self.EP}, TP: {self.TP}, SL: {self.SL}, High: {self.trend_high}, Low: {self.trend_low}")
                                        # Calculate Entry, L1, and L2 position size so L1 avg cost is at 0.441 and L2 at 0.29
                                        # 35% Account risk on 50x leverage
                                        self.Entry_size = 25/(self.SL-self.EP)
                                        # Check to see if we are in the time range. If so, store the order instead of placing it
                                        # if (dt.time(0, 0) <= current_time and current_time < dt.time(9, 0)):
                                            # self.stored_trade = (
                                            # 'buy', self.EP, self.Entry_size, self.TP, self.SL)
                                            # print("Long trade setup stored")
                                        # else:
                                            # self.Entry = self.buy(exectype=bt.Order.Limit, price=self.EP,
                                            #                       size=self.Entry_size)
                                            # print("Long Order placed")
                                        self.Entry = self.sell(exectype=bt.Order.Limit, price=self.EP, size=self.Entry_size)
                                        self.dir = 0
                                        return

    def stop(self):
        win_percentage = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        print(f'Total Trades: {self.total_trades}')
        print(f'Winning Trades: {self.winning_trades}')
        print(f'Winning Percentage: {win_percentage:.2f}%')
        profit = self.winning_trades * 400 - (self.total_trades-self.winning_trades) *100
        print(f'Profit: ${profit}')
        with open('TC1_strategy_results.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([self.params.sr_window_param,self.params.sr_req_param,self.params.min_size_param,self.params.max_size_param,self.params.prev_low_range_param,
                            self.params.low_candles_param,self.params.sr_range_param,self.params.fvg_range_param,
                             self.params.small_sr_param,self.params.ema_check_param, self.ema_200_check, self.total_trades, self.winning_trades,
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

    # Load the data
    """data = btfeeds.GenericCSVData(
        dataname='matic_usd_5min_data.csv',

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
    )"""

    # Call cerebro to run the backtest
    cerebro = bt.Cerebro()
    data_files = ['data_5min/matic_usd_5min_data.csv', 'data_5min/link_usd_5min_data.csv', 'data_5min/sol_usd_5min_data.csv']

    for data_file in data_files:
        data = btfeeds.GenericCSVData(
            dataname=data_file,
            nullvalue=0.0,
            compression=5,
            timeframe=bt.TimeFrame.Minutes,
            datetime=0,
            high=1,
            low=2,
            open=3,
            close=4,
            volume=5,
            openinterest=-1
        )
        cerebro.adddata(data)
    cerebro.optstrategy(
        TC1,
        small_sr_param=[4],
        sr_window_param=[-12],
        sr_req_param=[3],
        min_size_param=[0.015],
        max_size_param=[0.04, 0.06],
        prev_low_range_param=[48],
        low_candles_param=[6, 8, 10],
        sr_range_param=[0.0006, 0.0008],
        fvg_range_param=[0.0012],
        ema_check_param=[True],
        ema_200_param=[False, True],
    )
    # Check RSI divergence
    # Check end of the trend
    # Check for 15/30m FVGs instead
    cerebro.broker.setcash(cash)
    cerebro.broker.set_slippage_perc(0.0001)
    cerebro.broker.setcommission(commission=0.000)
    # cerebro.addsizer(bt.sizers.PercentSizer, percents=risk)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="areturn")
    results = cerebro.run(maxcpus=8)
    # cerebro.plot(style='candlestick', volume=False, grid=True, subplot=True)
    # print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # print(results[0].analyzers.areturn.get_analysis())
    filename = 'TC1_strategy_results.csv'
    data = load_csv_to_list(filename)

    # Sort data by the last element (win percentage)
    sorted_data = sort_data_by_last_element(data)

    # Print sorted data
    print("Sorted Strategy Results (by Winning Percentage):")
    print_sorted_data(sorted_data)