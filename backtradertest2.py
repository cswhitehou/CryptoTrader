import backtrader as bt
import datetime
import ccxt
import pandas as pd
import numpy as np


def fetch_historical_data(symbol, limit, exchange='phemex'):
    # Example for crypto data using ccxt
    exchange = ccxt.phemex()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='30m', limit=limit)
    data = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data.set_index('timestamp', inplace=True)
    return data





class SmaCross(bt.Strategy):
    def __init__(self):
        self.ema50 = bt.ind.EMA(period=50)
        self.rsi = bt.ind.RSI(period=14)
        self.dataclose = self.datas[0].close

    def next(self):
        if not self.position:  # not in the market
            if self.dataclose > self.ema50:
                if self.rsi < 70:
                    self.buy()  # enter long

        elif self.ema50 > self.dataclose:  # in the market & cross to the downside
            self.close()  # close long position

if __name__ == '__main__':
    df = fetch_historical_data('BTC/USDT', 1000)
    #df['rollhigh'] = df.High.rolling(15).max()
    #df['rolllow'] = df.Low.rolling(15).min()
    #df['mid'] = (df.rollhigh + df.rolllow)/2
    #df['highapproach'] = np.where(df.Close > df.rollhigh * 0.996, 1, 0)
    #df['close_a_mid'] = np.where(df.Close > df.mid, 1, 0)
    #df['midcross'] = df.close_a_mid.diff() == 1
    #in_position = False
    #buydates, selldates = [], []
    #for i in range(len(df)):
    #    if not in_position:
    #        if df.iloc[i].midcross:
    #            buydates.append(df.iloc[i+1].name)
    #            in_position = True
    #    if in_position:
    #        if df.iloc.highapproach:
    #            selldates.append(df.iloc[i+1].name)
    #            in_position = False

    cerebro = bt.Cerebro()

    feed = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(feed)

    cerebro.addstrategy(SmaCross)
    cerebro.broker.setcash(1000.0)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=50)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="areturn")
    teststrat = cerebro.run()
    cerebro.plot()
    print(teststrat[0].analyzers.areturn.get_analysis())
