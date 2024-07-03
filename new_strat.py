import pandas as pd
import backtrader as bt
import numpy as np
import ccxt
import csv
import os
import backtrader.feeds as btfeeds
from datetime import datetime, timedelta
from analyze_strat import load_csv_to_list, sort_data_by_last_element, print_sorted_data

class X1(bt.Strategy):
    params = (
        ('data_name', ''),  # File Name
        ('bollinger_period', 20),  # BB period
        ('bollinger_devfactor', 2),  # BB stddev factor
        ('macd1', 98),  # Fast length
        ('macd2', 99),  # Slow length
        ('macdsig', 30),  # Smoothing length
        ('rsi_period', 7),  # RSI period
        ('SL_range', 0.005),  # Where to put the candle based on the low/high
        ('win_multi', 1.5),  # RR ratio
        ('rsi_break', 5),  # How far the RSI has to break above 80/below 20
        ('rolling_range', 5),  # How far back to check for the low candle
    )
    # __init__ initializes all the variables to be used in the strategy when the strategy is loaded
    def __init__(self):
        # Initialize all the values
        self.ready_for_trade = 0
        self.ohlc4 = (self.data.open + self.data.high + self.data.low + self.data.close) / 4
        self.rolling_high = bt.indicators.Highest(self.data.close, period=self.params.rolling_range)
        self.rolling_low = bt.indicators.Lowest(self.data.close, period=self.params.rolling_range)
        self.EP = 0
        self.SL = 0
        self.TP = 0
        self.Entry_size = 0
        self.dir = 1
        self.StopLoss = None
        self.TakeProfit = None
        self.Entry = None
        self.accountSize = 1000
        self.total_trades = 0
        self.winning_trades = 0
        self.rsi = bt.indicators.RSI(self.ohlc4, period=self.params.rsi_period)
        # Bollinger Bands
        self.boll = bt.indicators.BollingerBands(
            self.data.close,
            period=20,
            devfactor=self.params.bollinger_devfactor
        )

        # MACD
        self.macd = bt.indicators.MACDHisto(
            self.ohlc4,
            period_me1=98,
            period_me2=99,
            period_signal=30,
        )

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
            self.accountSize+=trade.pnl
            # Clear and reset orders
            self.cancel_all_orders()
            self.clear_order_references()

    # This function updates trade #s and winning trades if SL/TP are hit
    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order == self.StopLoss:
                # print(f"STOP LOSS order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                self.total_trades += 1
                self.cancel_all_orders()
                self.clear_order_references()
                self.ready_for_trade = 0
            elif order == self.TakeProfit:
                # print(f"TAKE PROFIT order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                self.total_trades += 1
                self.winning_trades += 1
                self.cancel_all_orders()
                self.clear_order_references()
                self.ready_for_trade = 0
            # else:
                # print(f"Order executed, Price: {order.executed.price}, Size: {order.executed.size}")

    # Next is the main logic of the strategy and is called on with each new candle
    # To enter:
    # 1. Check if price has pushed into the BB
    # 2. RSI must break out
    # 3. RSI returns to normal range
    # 4. MACD histogram changes from dark to light color means ENTRY
    def next(self):
        if not self.position:
            # Check for RSI break IF BB has been pushed into
            if self.ready_for_trade == 1:
                if self.rsi > 80 + self.params.rsi_break:
                    self.ready_for_trade = 3
            elif self.ready_for_trade == 2:
                if self.rsi < 20 - self.params.rsi_break:
                    self.ready_for_trade = 4
            # Check for RSI back in normal range and switch from dark to light ONLY IF RSI has been broken
            # SHORT
            elif self.ready_for_trade == 3:
                if 0 < self.macd.lines.histo[0] < self.macd.lines.histo[-1] and self.rsi < 80:
                    # Check to make sure the last MACD was dark
                    if self.macd.lines.histo[-1] < self.macd.lines.histo[-2]:
                        self.ready_for_trade = 0
                    else:
                        self.SL = self.rolling_high * (1 + self.params.SL_range)
                        self.EP = self.data.close[0]
                        if abs(self.SL - self.EP)/self.EP < 0.001:  # Check if the range is too small
                            self.ready_for_trade = 0
                        else:
                            self.TP = (self.EP-self.SL)*self.params.win_multi + self.EP
                            self.Entry_size = 25/(self.SL-self.EP)
                            self.Entry = self.sell(size=self.Entry_size, exectype=bt.Order.Market)
                            self.StopLoss = self.buy(exectype=bt.Order.Stop, size=self.Entry_size, price=self.SL)
                            self.TakeProfit = self.buy(exectype=bt.Order.Limit, size=self.Entry_size, price=self.TP)
            # LONG
            elif self.ready_for_trade == 4:
                if 0 > self.macd.lines.histo[0] > self.macd.lines.histo[-1] and self.rsi > 20:
                    # Check to make sure the last MACD was dark
                    if self.macd.lines.histo[-1] > self.macd.lines.histo[-2]:
                        self.ready_for_trade = 0
                    else:
                        self.SL = self.rolling_low * (1 - self.params.SL_range)
                        self.EP = self.data.close[0]
                        if abs(self.SL - self.EP)/self.SL < 0.001:  # Check if the range is too small
                            self.ready_for_trade = 0
                        else:
                            self.TP = (self.EP-self.SL)*self.params.win_multi + self.EP
                            self.Entry_size = 25/(self.EP-self.SL)
                            self.Entry = self.buy(size=self.Entry_size, exectype=bt.Order.Market)
                            self.StopLoss = self.sell(exectype=bt.Order.Stop, size=self.Entry_size, price=self.SL)
                            self.TakeProfit = self.sell(exectype=bt.Order.Limit, size=self.Entry_size, price=self.TP)
            # Check if BB has been pushed into
            if self.ready_for_trade == 0:
                if self.data.high[0] >= self.boll.lines.top:
                    self.ready_for_trade = 1
                elif self.data.low[0] <= self.boll.lines.bot:
                    self.ready_for_trade = 2

    # This function is called at the end of every strategy and records the parameters and results in a csv
    def stop(self):
        win_percentage = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        print(f'Total Trades: {self.total_trades}')
        print(f'Winning Trades: {self.winning_trades}')
        print(f'Winning Percentage: {win_percentage:.2f}%')
        profit = self.winning_trades * 25 * self.params.win_multi - (self.total_trades-self.winning_trades) * 25
        print(f'Profit: ${profit}')
        with open('X1_strategy_results.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([self.params.data_name, self.params.bollinger_devfactor,self.params.rsi_period,
                             self.params.SL_range, self.params.win_multi, self.params.rsi_break, self.params.rolling_range,
                            self.total_trades, self.winning_trades,
                             win_percentage, profit])

if __name__ == '__main__':
    # Create variable
    exchange = 'phemex'
    coin = 'BTC/USDT'
    cash = 10000000.0
    risk = 5

    # Call cerebro to run the backtest
    # List of all the files
    data_files = ['data_5min/matic_usd_1min_data.csv',  'data_5min/ada_usd_1min_data.csv',  'data_5min/atom_usd_1min_data.csv',
                  'data_5min/apt_usd_1min_data.csv',  'data_5min/dot_usd_1min_data.csv', 'data_5min/link_usd_1min_data.csv',
                  'data_5min/xrp_usd_1min_data.csv', 'data_5min/sol_usd_1min_data.csv']

    for data_file in data_files:
        data = btfeeds.GenericCSVData(
            dataname=data_file,
            nullvalue=0.0,
            compression=1,
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
            X1,
            bollinger_period=[20],
            bollinger_devfactor=[2],
            macd1=[98],
            macd2=[99],
            macdsig=[30],
            rsi_period=[7],
            SL_range=[0.0002, 0.0005, 0.001, 0.005],
            win_multi=[1.5, 2.5],
            rsi_break=[0,3,5,7],
            rolling_range=[5,7,9],
            data_name=[data_file],
        )
        cerebro.broker.setcash(cash)
        cerebro.broker.set_slippage_perc(0.0001)
        cerebro.broker.setcommission(commission=0.000)
        # cerebro.addsizer(bt.sizers.PercentSizer, percents=risk)
        cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="areturn")
        results = cerebro.run(maxcpus=8)
        # cerebro.plot(style='candlestick', volume=False, grid=True, subplot=True)
    # print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # print(results[0].analyzers.areturn.get_analysis())
    filename = 'X1_strategy_results.csv'
    data = load_csv_to_list(filename)

    # Sort data by the last element (win percentage)
    sorted_data = sort_data_by_last_element(data)

    # Print sorted data
    print("Sorted Strategy Results (by Winning Percentage):")
    print_sorted_data(sorted_data)