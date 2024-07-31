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

class HeikinAshi(bt.Indicator):
    lines = ('ha_open', 'ha_high', 'ha_low', 'ha_close')
    plotinfo = dict(subplot=False)
    plotlines = dict(
        ha_open=dict(_name='HA_Open'),
        ha_high=dict(_name='HA_High'),
        ha_low=dict(_name='HA_Low'),
        ha_close=dict(_name='HA_Close'),
    )

    def __init__(self):
        self.addminperiod(1)

        # Calculate the Heikin Ashi close value
        self.lines.ha_close = (self.data.open + self.data.high + self.data.low + self.data.close) / 4

        # Calculate the Heikin Ashi open value
        self.lines.ha_open = bt.If(
            len(self.data) <= 1,
            (self.data.open + self.data.close) / 2,
            (self.lines.ha_open(-1) + self.lines.ha_close(-1)) / 2
        )

        # Calculate the Heikin Ashi high value
        self.lines.ha_high = bt.Max(self.data.high, self.lines.ha_open, self.lines.ha_close)

        # Calculate the Heikin Ashi low value
        self.lines.ha_low = bt.Min(self.data.low, self.lines.ha_open, self.lines.ha_close)


class TR1(bt.Strategy):
    params = (
        ('consecutive_candles', -7),
        ('RR', 2),
        ('rsi_period', 14),
        ('rsi_break', 0),
        ('data_name', ''), # File name
    )
    # __init__ initializes all the variables to be used in the strategy when the strategy is loaded
    def __init__(self):
        # Initialize all the values
        self.rolling_high = bt.indicators.Highest(self.data.high, period=6)
        self.rolling_low = bt.indicators.Lowest(self.data.low, period=6)
        self.trend_low = 0
        self.trend_high = 0
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
        self.total_trades = 0
        self.winning_trades = 0
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.consecutive_candles_check = 0
        self.ha = bt.indicators.HeikinAshi(self.data)
        self.broker.set_coc(True)

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
                self.sell(size=current_position_size)
            elif current_position_size < 0:
                self.buy(size=abs(current_position_size))
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
            elif order == self.TakeProfit:
                # print(f"TAKE PROFIT order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                self.total_trades += 1
                self.winning_trades += 1
                self.cancel_all_orders()
                self.clear_order_references()
            # else:
                # print(f"Order executed, Price: {order.executed.price}, Size: {order.executed.size}")
                # print(f'{self.EP}')

    # Next is the main logic of the strategy and is called on with each new candle
    # To enter:
    # 1. 7 Heikin Ashi candles in a row of the same color
    # 2. RSI overbought/oversold
    # 3. Candle closes in different color
    def next(self):
        # Create the 1-hour data
        if not self.position:
            current_time = self.data.datetime.time(0)  # Get the time
            # SHORT
            # print(current_time)
            # print(f'{self.ha.lines.ha_open[0]} {self.ha.lines.ha_high[0]} {self.ha.lines.ha_low[0]} {self.ha.lines.ha_close[0]}')
            if self.ha.lines.ha_close[0] > self.ha.lines.ha_open[0]:
                for i in range(self.params.consecutive_candles, -1):
                    if self.ha.lines.ha_close[i] > self.ha.lines.ha_open[i]:
                        return
                for i in range(-4, -1):
                    if self.rsi[i] < (30-self.params.rsi_break):
                        self.EP = self.data.close[0]
                        self.TP = self.rolling_low * 1
                        if abs(self.EP-self.TP) > 0.004:
                            self.SL = (self.EP-self.TP)*self.params.RR + self.EP
                            self.Entry_size = 25/abs(self.EP-self.SL)
                            self.Entry = self.sell(size=self.Entry_size, exectype=bt.Order.Market)
                            self.StopLoss = self.buy(exectype=bt.Order.Stop, size=self.Entry_size, price=self.SL)
                            self.TakeProfit = self.buy(exectype=bt.Order.Limit, size=self.Entry_size, price=self.TP)
                        return
            # LONG
            if self.ha.lines.ha_close[0] < self.ha.lines.ha_open[0]:
                for i in range(self.params.consecutive_candles, -1):
                    if self.ha.lines.ha_close[i] < self.ha.lines.ha_open[i]:
                        return
                for i in range(-4, -1):
                    if self.rsi[i] > (70+self.params.rsi_break):
                        self.EP = self.data.close[0]
                        self.TP = self.rolling_high * 1
                        if abs(self.EP-self.TP) > 0.004:
                            self.SL = (self.EP-self.TP)*self.params.RR + self.EP
                            self.Entry_size = 25/abs(self.SL-self.EP)
                            self.Entry = self.buy(size=self.Entry_size, exectype=bt.Order.Market)
                            self.StopLoss = self.sell(exectype=bt.Order.Stop, size=self.Entry_size, price=self.SL)
                            self.TakeProfit = self.sell(exectype=bt.Order.Limit, size=self.Entry_size, price=self.TP)
                        return

    # This function is called at the end of every strategy and records the parameters and results in a csv
    def stop(self):
        win_percentage = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        print(f'Total Trades: {self.total_trades}')
        print(f'Winning Trades: {self.winning_trades}')
        print(f'Winning Percentage: {win_percentage:.2f}%')
        expected_win_percentage = self.params.RR/(1+self.params.RR) * 100
        edge_on_market = win_percentage-expected_win_percentage
        print(f'Expected Win Percentage: {expected_win_percentage:.2f}%')
        print(f'Edge on Market: {edge_on_market:.2f}%')
        profit = self.winning_trades * 25 - (self.total_trades-self.winning_trades) * 25 * self.params.RR
        print(f'Profit: ${profit}')
        with open('ReverseTR1_strategy_results.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([self.params.data_name, self.params.consecutive_candles, self.params.RR, self.params.rsi_period,
                             self.params.rsi_break, self.total_trades, self.winning_trades,
                             expected_win_percentage, win_percentage, edge_on_market, profit])

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
            TR1,
            consecutive_candles=[-5, -7, -9],
            RR=[1, 1.5, 2, 3],
            rsi_period=[7, 14],
            rsi_break=[0, 3, 5],
            data_name=[data_file],
        )
        # cerebro.addstrategy(TR1)
    # Check RSI divergence
    # Check end of the trend
    # Check for 15/30m FVGs instead
    # Check if price above 15m, 1h 200 EMA
        cerebro.broker.setcash(cash)
        cerebro.broker.set_slippage_perc(0.000)
        cerebro.broker.setcommission(commission=0.000)
        # cerebro.addsizer(bt.sizers.PercentSizer, percents=risk)
        cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="areturn")
        results = cerebro.run(maxcpus=8)
        # cerebro.plot(style='candlestick', volume=False, grid=True, subplot=True)
    # print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # print(results[0].analyzers.areturn.get_analysis())
    filename = 'TR1_strategy_results2.csv'
    data = load_csv_to_list(filename)

    # Sort data by the last element (win percentage)
    sorted_data = sort_data_by_last_element(data)

    # Print sorted data
    print("Sorted Strategy Results (by Winning Percentage):")
    print_sorted_data(sorted_data)