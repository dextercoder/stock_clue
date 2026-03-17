import backtrader as bt
import pandas as pd
import os
import argparse

class SimpleMA(bt.Strategy):
    params = (
        ('maperiod', 15),
    )

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.maperiod)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')

    def next(self):
        self.log(f'Close, {self.dataclose[0]:.2f}')
        if self.order:return
        if not self.position:
            if self.dataclose[0] > self.sma[0]:
                self.log(f'BUY CREATE, {self.dataclose[0]:.2f}')
                self.order = self.buy()
        else:
            if self.dataclose[0] < self.sma[0]:
                self.log(f'SELL CREATE, {self.dataclose[0]:.2f}')
                self.order = self.sell()

class BottomBreakoutStrategy(bt.Strategy):
    params = (
        ('lookback_days', 30),  # 回顾周期
        ('max_down_days', 3),   # 连续下跌天数
        ('big_candle_ratio', 0.05),  # 大阳线涨幅比例
        ('buy_range', 0.02),    # 买入价格区间
        ('target_profit', 0.08), # 目标盈利8%
        ('stop_loss_ratio', 0.03),  # 止损比例3%
        ('buy_amount', 50000),   # 每次买入金额5万元
    )

    def __init__(self):
        # 为每只股票创建独立的状态变量
        self.stock_data = {}
        for i, data in enumerate(self.datas):
            stock_name = data._name if hasattr(data, '_name') else f'stock_{i}'
            self.stock_data[stock_name] = {
                'data': data,
                'order': None,
                'buyprice': None,
                'buycomm': None,
                'target_sell_price': None,
                'stop_loss_price': None,
                'bottom_price': None,
                'bought': False
            }

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        # 获取股票名称
        stock_name = order.data._name if hasattr(order.data, '_name') else f'stock_{self.datas.index(order.data)}'
        stock_info = self.stock_data[stock_name]
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'[{stock_name}] 买入成交: {order.executed.price:.2f}')
                stock_info['buyprice'] = order.executed.price
                stock_info['buycomm'] = order.executed.comm
                stock_info['target_sell_price'] = stock_info['buyprice'] * (1 + self.params.target_profit)
                stock_info['stop_loss_price'] = stock_info['buyprice'] * (1 - self.params.stop_loss_ratio)
                stock_info['bought'] = True
            else:
                self.log(f'[{stock_name}] 卖出成交: {order.executed.price:.2f}')
                stock_info['bought'] = False
                stock_info['bottom_price'] = None
                stock_info['stop_loss_price'] = None
        # 移除被取消/保证金不足/拒绝的订单日志
        stock_info['order'] = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        # 移除交易利润日志，因为用户只需要底、买入和卖出的信息
        pass

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')

    def find_bottoms(self, data):
        """寻找符合条件的底部"""
        if len(data) < self.params.lookback_days:
            return None
        
        bottoms = []
        stock_name = data._name if hasattr(data, '_name') else f'stock_{self.datas.index(data)}'
        
        # 遍历回顾周期内的每一天
        for i in range(-self.params.lookback_days + 1, 1):
            try:
                # 检查是否有连续下跌
                down_days = 0
                for j in range(1, self.params.max_down_days + 1):
                    if data.close[i-j] > data.close[i-j+1]:
                        down_days += 1
                    else:
                        break
                
                # 如果有足够的连续下跌天数
                if down_days >= self.params.max_down_days:
                    # 检查是否是大阳线
                    candle_ratio = (data.close[i] - data.open[i]) / data.open[i]
                    if candle_ratio >= self.params.big_candle_ratio and data.close[i] > data.open[i]:
                        # 记录大阳线收盘价下方50%的位置作为底部价格
                        bottom_price = data.close[i] * 0.5
                        bottoms.append(bottom_price)
            except IndexError:
                continue
        
        if bottoms:
            return min(bottoms)  # 返回最低的底部价格
        return None

    def next(self):
        # 为每只股票单独执行策略逻辑
        for stock_name, stock_info in self.stock_data.items():
            data = stock_info['data']
            
            if stock_info['order']:
                continue
            
            # 寻找底部
            current_bottom = self.find_bottoms(data)
            
            # 更新最低底部价格
            if current_bottom:
                if stock_info['bottom_price'] is None or current_bottom < stock_info['bottom_price']:
                    stock_info['bottom_price'] = current_bottom
                    self.log(f'[{stock_name}] 底: {stock_info["bottom_price"]:.2f}')
            
            # 买入逻辑
            if stock_info['bottom_price'] and not stock_info['bought']:
                buy_range_low = stock_info['bottom_price'] * (1 - self.params.buy_range)
                buy_range_high = stock_info['bottom_price'] * (1 + self.params.buy_range)
                
                if buy_range_low <= data.close[0] <= buy_range_high:
                    self.log(f'[{stock_name}] 买入: {data.close[0]:.2f}, 金额: {self.params.buy_amount:.2f}')
                    # 使用data参数指定要交易的股票
                    stock_info['order'] = self.buy(data=data, value=self.params.buy_amount)
            
            # 卖出逻辑
            if stock_info['bought']:
                # 目标盈利卖出
                if stock_info['target_sell_price'] and data.close[0] >= stock_info['target_sell_price']:
                    self.log(f'[{stock_name}] 卖出: {data.close[0]:.2f}, 目标盈利')
                    stock_info['order'] = self.sell(data=data)
                # 止损卖出
                elif stock_info['stop_loss_price'] and data.close[0] <= stock_info['stop_loss_price']:
                    self.log(f'[{stock_name}] 卖出: {data.close[0]:.2f}, 止损')
                    stock_info['order'] = self.sell(data=data)

class CSVDataLoader:
    @staticmethod
    def load_data(code, datapath):
        filename = os.path.join(datapath, f'{code}_daily.csv')
        if not os.path.exists(filename):
            raise FileNotFoundError(f'Data file not found: {filename}')
        df = pd.read_csv(filename)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        data = bt.feeds.PandasData(
            dataname=df,
            datetime=None,
            openinterest=-1
        )
        return data

def run_backtest(code, datapath, strategy_class=SimpleMA, params=None, cash=100000.0):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy_class, **(params or {}))
    data = CSVDataLoader.load_data(code, datapath)
    cerebro.adddata(data)
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=0.001)
    print(f'Initial Portfolio Value: {cerebro.broker.getvalue():.2f}')
    cerebro.run()
    print(f'Final Portfolio Value: {cerebro.broker.getvalue():.2f}')
    # cerebro.plot(style='candlestick')  # 注释掉图形绘制部分

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Stock Backtesting Tool')
    parser.add_argument('--code', default='000001', help='Stock code (default: 000001)')
    parser.add_argument('--strategy', default='simplema', choices=['simplema', 'bottombreakout'], 
                        help='Strategy to use (default: simplema)')
    parser.add_argument('--data', default='./daily_data_cache', help='Path to data directory')
    parser.add_argument('--cash', type=float, default=100000.0, help='Initial cash')
    
    # 策略参数
    parser.add_argument('--lookback', type=int, default=30, help='Lookback days for bottom breakout')
    parser.add_argument('--maxdown', type=int, default=3, help='Max consecutive down days')
    parser.add_argument('--bigcandle', type=float, default=0.05, help='Big candle ratio')
    parser.add_argument('--buyrange', type=float, default=0.02, help='Buy price range')
    parser.add_argument('--targetprofit', type=float, default=0.08, help='Target profit ratio')
    parser.add_argument('--stoploss', type=float, default=0.03, help='Stop loss ratio (default: 0.03)')
    parser.add_argument('--buyamount', type=float, default=50000.0, help='Buy amount per trade (default: 50000.0)')
    parser.add_argument('--maperiod', type=int, default=15, help='MA period for SimpleMA')
    
    args = parser.parse_args()
    
    # 选择策略
    if args.strategy == 'simplema':
        strategy_class = SimpleMA
        strategy_params = {'maperiod': args.maperiod}
    else:
        strategy_class = BottomBreakoutStrategy
        strategy_params = {
            'lookback_days': args.lookback,
            'max_down_days': args.maxdown,
            'big_candle_ratio': args.bigcandle,
            'buy_range': args.buyrange,
            'target_profit': args.targetprofit,
            'stop_loss_ratio': args.stoploss,
            'buy_amount': args.buyamount
        }
    
    print(f"Running backtest with {args.strategy} strategy...")
    print(f"Stock code: {args.code}")
    print(f"Initial cash: {args.cash:.2f}")
    print()
    
    run_backtest(
        code=args.code,
        datapath=args.data,
        strategy_class=strategy_class,
        params=strategy_params,
        cash=args.cash
    )