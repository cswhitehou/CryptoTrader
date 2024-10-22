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
def find_support_resistance(df, window=4): # window is the number of candles needed to be considered S/R
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


class ReverseTC1(bt.Strategy):
    params = (
        ('min_size_param', 0.015), # Minimum size for the range
        ('max_size_param', 0.05), # Maximum size for the range
        ('prev_low_range_param', 48), # How far back to check for the previous low
        ('low_candles_param', 8), # How many candles are required to be considered a trend low
        ('FVG_days_param', 3), # How many days back are looked at for FVGs
        ('EPrice', 0.382), # The Fib level for entry
        ('TPPrice', 0.17), # The Fib level for take profit
        ('SLPrice', 1.272), # The Fib level for stop loss
        ('data_name', ''), # File name
    )
    # __init__ initializes all the variables to be used in the strategy when the strategy is loaded
    def __init__(self):
        # Initialize all the values
        self.ema20 = bt.ind.EMA(period=20)
        self.ema50 = bt.ind.EMA(period=50)
        self.ema200 = bt.ind.EMA(period=200)
        self.ema600 = bt.ind.EMA(period=600)
        self.rolling_high = bt.indicators.Highest(self.data.high, period=12*4)
        self.rolling_low = bt.indicators.Lowest(self.data.low, period=12*4)
        self.trend_low = 0
        self.first_high = 0
        self.higher_low = 0
        self.trend_high = 0
        self.last_resistance = 0
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
        self.min_size = self.params.min_size_param
        self.max_size = self.params.max_size_param
        self.prev_low_range = self.params.prev_low_range_param
        self.low_candles = self.params.low_candles_param

    # This function cancels all orders
    def cancel_all_orders(self):
        # Cancel all open orders
        for order in self.broker.get_orders_open():
            self.cancel(order)

    # This function sets all orders to None
    def clear_order_references(self):
        self.StopLoss = None
        self.TakeProfit = None
        self.Entry = None

    # This function is called when a trade is completed and updates profit
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
            self.accountSize += trade.pnl
            # Clear and reset orders
            self.cancel_all_orders()
            self.clear_order_references()

    # This function places take profits and stop losses if the entry is filled
    def notify_order(self, order):
        if order.status in [order.Completed]:
            # print(f"Order executed, Price: {order.executed.price}, Size: {order.executed.size}")
            if order == self.Entry and self.dir == 1:  # SHORT
                # print(f"BUY LONG order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                if not self.TakeProfit:
                    self.TakeProfit = self.buy(exectype=bt.Order.Limit, price=self.TP, size=order.executed.size)
                    # print("TP LONG placed")
                if not self.StopLoss:
                    self.StopLoss = self.buy(exectype=bt.Order.Stop, price=self.SL, size=order.executed.size)
                    # print("SL LONG Placed")
            if order == self.Entry and self.dir == 0:  # LONG
                # print(f"BUY SHORT order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                if not self.TakeProfit:
                    self.TakeProfit = self.sell(exectype=bt.Order.Limit, price=self.TP, size=order.executed.size)
                    # print("TP SHORT placed")
                if not self.StopLoss:
                    self.StopLoss = self.sell(exectype=bt.Order.Stop, price=self.SL, size=order.executed.size)
                    # print("SL SHORT Placed")
            if order == self.StopLoss:
                #print(f"STOP LOSS order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                self.total_trades += 1
                self.cancel_all_orders()
                self.clear_order_references()
            if order == self.TakeProfit:
                #print(f"TAKE PROFIT order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                self.total_trades += 1
                self.winning_trades += 1
                self.cancel_all_orders()
                self.clear_order_references()

    # This function finds fair value gaps
    def get_fair_value_gaps(self):
        if self.data1h[-1][1] > self.data1h[-3][2]:
            # Bullish FVG
            fvg = (self.data1h[-1][0], self.data1h[-3][2], self.data1h[-1][1], (self.data1h[-1][1]+self.data1h[-3][2])/2, 'bullish', (self.data1h[-1][1]-self.data1h[-3][2])/self.data1h[-3][2])
            if fvg not in self.FVGs:
                self.FVGs.append(fvg)
                # print("FVG appended")
                # print(fvg)
        elif self.data1h[-1][2] < self.data1h[-3][1]:
            # Bearish FVG
            fvg = (self.data1h[-1][0], self.data1h[-1][2], self.data1h[-3][1], (self.data1h[-3][1]+self.data1h[-1][2])/2, 'bearish', (self.data1h[-3][1]-self.data1h[-1][2])/self.data1h[-3][1])
            if fvg not in self.FVGs:
                self.FVGs.append(fvg)
                # print("FVG appended")
                # print(fvg)
        # Check if the FVG has been filled
        """for fvg in self.FVGs:
            if self.data.high[0] > fvg[2] and fvg[4] == 'bearish':
                self.FVGs.remove(fvg)
            elif self.data.low[0] < fvg[2] and fvg[4] == 'bullish':
                self.FVGs.remove(fvg)"""
        current_date = self.data.datetime.datetime(0)  # Get the current date from the data feed
        lookback_date = current_date - timedelta(days=self.params.FVG_days_param)
        # Check if any of the FVGs are too old
        for date in self.FVGs:
            if lookback_date > date[0]:
                self.FVGs.remove(date)
                # print(f'{date} removed from S/R')

    # Check for Hammer Candles
    # RSI Divergence

    # Next is the main logic of the strategy and is called on with each new candle
    # To enter:
    # 1. New High
    # 2. Find a low
    # 3. 1hr FVG below/above TP
    # 4. Check for RSI Divergence
    def next(self):
        # Create the 1-hour data
        if self.data.datetime.datetime(0).minute == 0:
            low_1h = self.data.low.get(size=12, ago=-1)
            high_1h = self.data.high.get(size=12, ago=-1)
            self.data1h.append((self.data.datetime.datetime(0), min(low_1h), max(high_1h)))
        if len(self.data1h) > 3:
            self.get_fair_value_gaps()
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
            # SHORT
            elif self.data.high[0] == self.rolling_high and self.data.high[0] - max([self.data.close[0], self.data.open[0]]) > (max([self.data.close[0], self.data.open[0]]) - self.data.low[0]): # Hammer Candle
                self.trend_high = self.data.high[0]
                # Find most recent support for the low
                for i in range(6, self.prev_low_range):
                    window_low = self.data.low.get(size=self.low_candles, ago=-i)
                    window_low2 = self.data.low.get(size=i + 10, ago=-1)
                    if self.data.low[-i] == min(window_low):
                        self.trend_low = self.data.low[-i]
                        # if max(self.rsi.get(size=12)) > 72:
                            #for j in range(8, round(i*1.8)):
                                #if max(self.rsi.get(size=4)) < self.rsi[-j] and self.data.high[0] > self.data.high[-j]: # RSI Divergence
                        # if not (self.rsi > self.prev_rsi > 70):
                        if self.min_size < (self.trend_high - self.trend_low) / self.trend_low < self.max_size:
                            self.EP = (self.trend_high - self.trend_low) * self.params.EPrice + self.trend_low
                            self.SL = (self.trend_high - self.trend_low) * self.params.SLPrice + self.trend_low
                            self.TP = (self.trend_high - self.trend_low) * self.params.TPPrice + self.trend_low

                            for fvg in self.FVGs:
                                if self.TP > fvg[3] and self.EP < self.ema600:
                                    #print(f"E: {self.EP}, TP: {self.TP}, SL: {self.SL}, High: {self.trend_high}, Low: {self.trend_low}")
                                    self.Entry_size = 25/(self.EP-self.SL)
                                    self.Entry = self.sell(exectype=bt.Order.StopLimit, price=self.EP, size=self.Entry_size)
                                    self.dir = 1
                                    return
            # LONG
            elif self.data.low[0] == self.rolling_low and (self.data.high[0] - min([self.data.close[0], self.data.open[0]])) < min([self.data.close[0], self.data.open[0]]) - self.data.low[0]: # Hammer Candle
                self.trend_low = self.data.low[0]
                # Find most recent support for the low
                for i in range(6, self.prev_low_range):
                    window_high = self.data.high.get(size=self.low_candles, ago=-i)
                    window_high2 = self.data.high.get(size=i+10, ago=-1)
                    if self.data.high[-i] == max(window_high):
                        self.trend_high = self.data.high[-i]
                        # if min(self.rsi.get(size=12)) < 28:
                            # for j in range(8, round(i*1.8)):
                                # if min(self.rsi.get(size=4)) > self.rsi[-j] and self.data.low[0] < self.data.low[-j]: # RSI Divergence
                        # if not (self.rsi < self.prev_rsi < 70):
                        if self.min_size < (self.trend_high - self.trend_low) / self.trend_high < self.max_size:
                            self.EP = (self.trend_low-self.trend_high) * self.params.EPrice + self.trend_high
                            self.SL = (self.trend_low - self.trend_high) * self.params.SLPrice + self.trend_high
                            self.TP = (self.trend_low - self.trend_high) * self.params.TPPrice + self.trend_high

                            for fvg in self.FVGs:
                                if self.TP < fvg[3] and self.EP > self.ema600:
                                    # print(f"E: {self.EP}, TP: {self.TP}, SL: {self.SL}, High: {self.trend_high}, Low: {self.trend_low}")
                                    self.Entry_size = 25/(self.SL-self.EP)
                                    self.Entry = self.buy(exectype=bt.Order.StopLimit, price=self.EP, size=self.Entry_size)
                                    self.dir = 0
                                    return

    # This function is called at the end of every strategy and records the parameters and results in a csv
    def stop(self):
        win_percentage = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        RR = abs(self.params.EPrice-self.params.TPPrice)/abs(self.params.EPrice-self.params.SLPrice)
        expecteded_win_percentage = 1/(1+RR) * 100 if self.total_trades > 0 else 0
        print(f'Total Trades: {self.total_trades}')
        print(f'Winning Trades: {self.winning_trades}')
        print(f'Expected Winning Percentage: {expecteded_win_percentage:.2f}%')
        print(f'Winning Percentage: {win_percentage:.2f}%')
        edge = win_percentage - expecteded_win_percentage
        print(f'Edge on Market: {edge:.2f}%')
        profit = self.winning_trades * 25 * RR - (self.total_trades-self.winning_trades) * 25
        print(f'Profit: ${profit}')
        with open('tempReverseTC1_strategy_results.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([self.params.data_name, self.params.min_size_param, self.params.max_size_param, self.params.prev_low_range_param,
                             self.params.low_candles_param, self.params.FVG_days_param,
                             self.params.EPrice, self.params.TPPrice, self.params.SLPrice, self.total_trades, self.winning_trades,
                             expecteded_win_percentage, win_percentage, edge, profit])

# Check for RSI Divergence

if __name__ == '__main__':
    # Create variable
    exchange = 'phemex'
    coin = 'BTC/USDT'
    cash = 10000000.0
    risk = 5


    # Call cerebro to run the backtest
    cerebro = bt.Cerebro()
    # List of all the files
    data_files = ['data_5min/dot_usd_5min_data4.csv', 'data_5min/link_usd_5min_data4.csv', 'data_5min/ada_usd_5min_data4.csv', 'data_5min/atom_usd_5min_data4.csv',
                'data_5min/sol_usd_5min_data4.csv', 'data_5min/xrp_usd_5min_data4.csv', 'data_5min/matic_usd_5min_data4.csv', 'data_5min/apt_usd_5min_data2.csv']

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
        # Choose the parameters
        cerebro.optstrategy(
            ReverseTC1,
            min_size_param=[0.015, 0.025],
            max_size_param=[0.06],
            prev_low_range_param=[50],
            low_candles_param=[8],
            FVG_days_param=[0.5,1,3],
            EPrice=[0.5, 0.382],
            TPPrice=[0, -0.17, -0.272],
            SLPrice=[0.618, 0.768, 1],
            data_name=[data_file],
        )
        # cerebro.addstrategy(TC1)
    # Check RSI divergence
        cerebro.broker.setcash(cash)
        cerebro.broker.set_slippage_perc(0.000)
        cerebro.broker.setcommission(commission=0.000)
        # cerebro.addsizer(bt.sizers.PercentSizer, percents=risk)
        cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="areturn")
        results = cerebro.run(maxcpus=4)
        # cerebro.plot(style='candlestick', volume=False, grid=True, subplot=True)
    # print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # print(results[0].analyzers.areturn.get_analysis())
    filename = 'ReverseTC1_strategy_results.csv'
    data = load_csv_to_list(filename)

    # Sort data by the last element (win percentage)
    sorted_data = sort_data_by_last_element(data)

    # Print sorted data
    print("Sorted Strategy Results (by Winning Percentage):")
    print_sorted_data(sorted_data)