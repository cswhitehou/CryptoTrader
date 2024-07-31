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
        ('min_num',0),
        ('max_num', 100),
        ('min_range', 0.001),
        ('SL_max', 0.01),
        ('max_range', 0.5),
        ('ema_multi', 1),
        ('entry_diff', 0.0001),
        ('bars', 100),
        ('rsi_period', 7),  # RSI period
        ('loss_streak', 2),  # Max Loss streak in a single direction before switching
        ('SL_range', 0.005),  # Where to put the candle based on the low/high
        ('win_multi', 2.5),  # RR ratio
        ('rsi_break', 3),  # How far the RSI has to break above 80/below 20
        ('rolling_range', 11),  # How far back to check for the low candle
    )
    # __init__ initializes all the variables to be used in the strategy when the strategy is loaded
    def __init__(self):
        # Initialize all the values
        self.ema20 = bt.ind.EMA(period=20)
        self.ema50 = bt.ind.EMA(period=50)
        self.ema200 = bt.ind.EMA(period=200)
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
        self.consecutive_losses = 0
        self.lined_up_trades = 0
        self.ema_lineup = False
        self.past_bars = 0
        self.candles_count = 0
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        # Bollinger Bands
        self.boll = bt.indicators.BollingerBands(
            self.data.close,
            period=20,
            devfactor=self.params.bollinger_devfactor
        )

        # MACD
        self.macd = bt.indicators.MACDHisto(
            self.data.close,
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
                self.sell(size=abs(current_position_size))
            elif current_position_size < 0:
                self.buy(size=abs(current_position_size))
            self.accountSize+=trade.pnl
            # Clear and reset orders
            self.cancel_all_orders()
            self.clear_order_references()

    # This function updates trade #s and winning trades if SL/TP are hit
    def notify_order(self, order):
        if order.status in [order.Completed]:
            # print(f"Order executed, Price: {order.executed.price}, Size: {order.executed.size}")
            # self.Entry = None
            if order == self.StopLoss:
                # print(f"STOP LOSS order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                if abs(self.consecutive_losses) >= self.params.loss_streak:
                    self.consecutive_losses = 0
                self.total_trades += 1
                self.cancel_all_orders()
                self.clear_order_references()
                self.ready_for_trade = 0
                if self.dir == 1:
                    self.consecutive_losses += 1
                elif self.dir == 0:
                    self.consecutive_losses -= 1
                if self.position.size > 0:
                    self.sell(size=self.position.size)
                if self.position.size < 0:
                    self.buy(size=self.position.size)
            elif order == self.TakeProfit:
                # print(f"TAKE PROFIT order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                if self.ema_lineup:
                    self.lined_up_trades += 1
                self.total_trades += 1
                self.winning_trades += 1
                self.cancel_all_orders()
                self.clear_order_references()
                self.ready_for_trade = 0
                self.consecutive_losses = 0
                if self.position.size > 0:
                    self.sell(size=self.position.size)
                if self.position.size < 0:
                    self.buy(size=self.position.size)

    # Next is the main logic of the strategy and is called on with each new candle
    # To enter:
    # 1. Check if price has pushed into the BB
    # 2. RSI must break out
    # 3. RSI returns to normal range
    # 4. MACD histogram changes from dark to light color means ENTRY
    def next(self):
        current_datetime = self.data.datetime.datetime(0)
        self.candles_count += 1
        if 10000 * self.params.min_num < self.candles_count < 10000 * self.params.max_num + self.params.min_num * 10000:
            if not self.position:
                if self.Entry:
                    if self.dir == 0:
                        if self.data.high[0] > (self.EP - self.SL) + self.EP:
                            self.cancel_all_orders()
                            self.clear_order_references()
                    elif self.dir == 1:
                        if self.data.low[0] < (self.EP-self.SL) + self.EP:
                            self.cancel_all_orders()
                            self.clear_order_references()
                # Check for RSI break IF BB has been pushed into
                if self.ready_for_trade == 1:
                    if self.rsi > 80 + self.params.rsi_break:
                        self.ready_for_trade = 3
                        self.past_bars = 0
                    else:
                        self.past_bars += 1
                        if self.past_bars > self.params.bars:
                            self.ready_for_trade = 0
                elif self.ready_for_trade == 2:
                    if self.rsi < 20 - self.params.rsi_break:
                        self.ready_for_trade = 4
                        self.past_bars = 0
                    else:
                        self.past_bars += 1
                        if self.past_bars > self.params.bars:
                            self.ready_for_trade = 0
                # Check for RSI back in normal range and switch from dark to light ONLY IF RSI has been broken
                # SHORT
                elif self.ready_for_trade == 3:
                    if 0 < self.macd.lines.histo[0] < self.macd.lines.histo[-1] and self.rsi < 80:
                        # Check to make sure the last MACD was dark
                        if self.macd.lines.histo[-1] < self.macd.lines.histo[-2]:
                            self.ready_for_trade = 0
                        else:
                            self.EP = self.data.close[0] * (1+self.params.entry_diff)
                            self.SL = min([self.rolling_high * (1 + self.params.SL_range), self.EP * (1+self.params.SL_max)])
                            if self.params.max_range < abs(self.SL - self.EP)/self.EP or abs(self.SL - self.EP)/self.EP < self.params.min_range:  # Check if the range is too small
                                self.ready_for_trade = 0
                            else:
                                if self.EP < self.ema200:
                                    self.TP = (self.EP-self.SL)*self.params.win_multi*self.params.ema_multi + self.EP
                                    self.ema_lineup = True
                                else:
                                    self.TP = (self.EP-self.SL)*self.params.win_multi + self.EP
                                    self.ema_lineup = False
                                self.Entry_size = 25/(self.SL-self.EP)
                                self.Entry = self.sell(size=self.Entry_size, exectype=bt.Order.Limit, price=self.EP)
                                self.StopLoss = self.buy(exectype=bt.Order.Stop, size=self.Entry_size, price=self.SL)
                                self.TakeProfit = self.buy(exectype=bt.Order.Limit, size=self.Entry_size, price=self.TP)
                                self.dir = 1
                                self.past_bars = 0
                    else:
                        self.past_bars += 1
                        if self.past_bars > self.params.bars:
                            self.ready_for_trade = 0
                # LONG
                elif self.ready_for_trade == 4:
                    if 0 > self.macd.lines.histo[0] > self.macd.lines.histo[-1] and self.rsi > 20:
                        # Check to make sure the last MACD was dark
                        if self.macd.lines.histo[-1] > self.macd.lines.histo[-2]:
                            self.ready_for_trade = 0
                        else:
                            self.EP = self.data.close[0] * (1+self.params.entry_diff)
                            self.SL = max([self.rolling_low * (1 - self.params.SL_range), self.EP*(1-self.params.SL_max)])
                            # print(f'EP: {self.EP}, SL: {self.SL}')
                            if self.params.max_range < abs(self.SL - self.EP)/self.SL or abs(self.SL - self.EP)/self.SL < self.params.min_range:  # Check if the range is too small
                                self.ready_for_trade = 0
                            else:
                                if self.EP > self.ema200:
                                    self.TP = (self.EP-self.SL)*self.params.win_multi*self.params.ema_multi + self.EP
                                    self.ema_lineup = True
                                else:
                                    self.TP = (self.EP-self.SL)*self.params.win_multi + self.EP
                                    self.ema_lineup = False
                                self.Entry_size = 25/(self.EP-self.SL)
                                self.Entry = self.buy(size=self.Entry_size, exectype=bt.Order.Limit, price= self.EP)
                                self.StopLoss = self.sell(exectype=bt.Order.Stop, size=self.Entry_size, price=self.SL)
                                self.TakeProfit = self.sell(exectype=bt.Order.Limit, size=self.Entry_size, price=self.TP)
                                self.dir = 0
                                self.past_bars = 0
                    else:
                        self.past_bars += 1
                        if self.past_bars > self.params.bars:
                            self.ready_for_trade = 0
                # Check if BB has been pushed into
                if self.ready_for_trade < 3:
                    if self.data.high[0] >= self.boll.lines.top and self.consecutive_losses < self.params.loss_streak:
                        self.ready_for_trade = 1
                        self.past_bars = 0
                    elif self.data.low[0] <= self.boll.lines.bot and (-1 * self.consecutive_losses) < self.params.loss_streak:
                        self.ready_for_trade = 2
                        self.past_bars = 0

    # This function is called at the end of every strategy and records the parameters and results in a csv
    def stop(self):
        self.days = round(self.candles_count / (60*24))
        win_percentage = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        print(f'Total Trades: {self.total_trades}')
        print(f'Winning Trades: {self.winning_trades}')
        print(f'Winning Percentage: {win_percentage:.2f}%')
        expected_win_percentage = 1/(1+self.params.win_multi) * 100 if self.total_trades > 0 else 0
        print(f'Expected Winning Percentage: {expected_win_percentage:.2f}%')
        edge = win_percentage - expected_win_percentage
        print(f'Edge on Market: {edge:.2f}%')
        profit = self.winning_trades * 25 * self.params.win_multi - (self.total_trades-self.winning_trades) * 25 + self.lined_up_trades * 25 * (self.params.ema_multi-1)
        profit_per_day = round(profit/self.days)
        print(f'Profit: ${profit}')
        with open('X1_strategy_results.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([self.params.data_name, self.params.rsi_period,
                             # self.params.SL_max, self.params.max_range, self.params.entry_diff,self.params.SL_range,
                             self.params.win_multi, self.params.rsi_break, self.params.rolling_range,
                            self.total_trades, self.winning_trades, self.days, profit_per_day, expected_win_percentage,
                             win_percentage, edge, profit])


if __name__ == '__main__':
    # Create variable
    exchange = 'phemex'
    coin = 'BTC/USDT'
    cash = 10000000.0
    risk = 5

    # Check for EMAs in line after entry
    # Check multiple limit orders
    # Trail SL
    # Multiple Take profits
    # Only Long/Short


    # Call cerebro to run the backtest
    # List of all the files
    data_files = ['data_5min/apt_usd_1min_data2.csv', 'data_5min/matic_usd_1min_data.csv', 'data_5min/sol_usd_1min_data.csv',  'data_5min/ada_usd_1min_data.csv',  'data_5min/atom_usd_1min_data.csv',
                 'data_5min/dot_usd_1min_data.csv', 'data_5min/link_usd_1min_data.csv',
                 'data_5min/xrp_usd_1min_data.csv']
    """data_files = ['data_5min/matic_usd_1min_data3.csv',
                  'data_5min/sol_usd_1min_data3.csv', 'data_5min/dot_usd_1min_data3.csv']"""
    data_folder = 'data_1min'

    # List to hold all the data feeds
    data_feeds = []

    # Iterate over all files in the directory
    for data_file in os.listdir(data_folder):
        # Construct the full file path
        file_path = os.path.join(data_folder, data_file)

        # Ensure it's a file (and not a subdirectory or other)
        if os.path.isfile(file_path):
            data = btfeeds.GenericCSVData(
                dataname=file_path,
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
            rsi_period=[7, 14],
            min_num=[0],
            max_num=[100],
            SL_max=[1],
            min_range=[0.001],
            ema_multi=[1],
            bars=[100],
            max_range=[0.5],
            loss_streak=[100],
            SL_range=[0.0005, 0.001, 0.005],
            entry_diff=[0.0001],
            win_multi=[1.5, 2.5],
            rsi_break=[0, 3, 5],
            rolling_range=[12, 20],
            data_name=[data_file],
        )
        # cerebro.addstrategy(X1)
        cerebro.broker.setcash(cash)
        cerebro.broker.set_slippage_perc(0.0001)
        cerebro.broker.setcommission(commission=0.000)
        # cerebro.addsizer(bt.sizers.PercentSizer, percents=risk)
        cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="areturn")
        results = cerebro.run(maxcpus=8)
        # cerebro.plot(style='candlestick', volume=False, grid=True, subplot=True)
    # print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # print(results[0].analyzers.areturn.get_analysis())
    """filename = 'X1_strategy_results.csv'
    data = load_csv_to_list(filename)

    # Sort data by the last element (win percentage)
    sorted_data = sort_data_by_last_element(data)

    # Print sorted data
    print("Sorted Strategy Results (by Winning Percentage):")
    print_sorted_data(sorted_data)"""