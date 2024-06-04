import backtrader as bt
import datetime
import yfinance as yf
import ccxt
import pandas as pd


def fetch_historical_data(symbol, start_date, end_date, exchange='phemex'):
    # Example for crypto data using ccxt
    exchange = ccxt.phemex()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=1000)
    data = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data.set_index('timestamp', inplace=True)
    return data


df = fetch_historical_data('BTC/USDT', '2020-01-01', '2021-01-01')

cerebro = bt.Cerebro()


feed = bt.feeds.PandasData(dataname=df)
cerebro.adddata(feed)

class SmaCross(bt.Strategy):
    def __init__(self):
        sma1 = bt.ind.SMA(period=50)  # fast moving average
        sma2 = bt.ind.SMA(period=100)  # slow moving average
        self.crossover = bt.ind.CrossOver(sma1, sma2)  # crossover signal

    def next(self):
        if not self.position:  # not in the market
            if self.crossover > 0:  # if fast crosses slow to the upside
                self.buy()  # enter long

        elif self.crossover < 0:  # in the market & cross to the downside
            self.close()  # close long position

if __name__ == '__main__':
    df = fetch_historical_data('BTC/USDT', '2020-01-01', '2021-01-01')

    cerebro = bt.Cerebro()

    print(df)
    feed = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(feed)

    cerebro.addstrategy(SmaCross)
    cerebro.broker.setcash(1000.0)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=50)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="areturn")
    teststrat = cerebro.run()
    cerebro.plot()
    print(teststrat[0].analyzers.areturn.get_analysis())
