import backtrader as bt
import pandas as pd
import os
import numpy as np

class BottomBreakoutStrategy(bt.Strategy):
    params = (
        ('lookback_days', 50),  # 回顾周期
        ('max_down_days', 3),   # 连续下跌天数
        ('big_candle_ratio', 0.05),  # 大阳线涨幅比例
        ('buy_range', 0.02),    # 买入价格区间
        ('target_profit', 0.08), # 目标盈利8%
        ('stop_loss_ratio', 0.03),  # 止损比例3%
        ('buy_amount', 50000),   # 每次买入金额5万元
    )

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.target_sell_price = None
        self.stop_loss_price = None  # 止损价格
        self.bottom_price = None  # 记录最低的底部价格
        self.bought = False

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
                self.target_sell_price = self.buyprice * (1 + self.params.target_profit)
                self.stop_loss_price = self.buyprice * (1 - self.params.stop_loss_ratio)  # 设置止损价格
                self.bought = True
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                self.bought = False
                self.bottom_price = None  # 重置底部价格
                self.stop_loss_price = None  # 重置止损价格
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

    def find_bottoms(self):
        """寻找符合条件的底部"""
        if len(self) < self.params.lookback_days:
            return None
        
        bottoms = []
        
        # 遍历回顾周期内的每一天
        for i in range(-self.params.lookback_days + 1, 1):
            try:
                # 检查是否有连续下跌
                down_days = 0
                for j in range(1, self.params.max_down_days + 1):
                    if self.dataclose[i-j] > self.dataclose[i-j+1]:
                        down_days += 1
                    else:
                        break
                
                # 如果有足够的连续下跌天数
                if down_days >= self.params.max_down_days:
                    # 检查是否是大阳线
                    # 使用收盘价相对于开盘价的涨幅来定义大阳线
                    candle_ratio = (self.dataclose[i] - self.dataopen[i]) / self.dataopen[i]
                    if candle_ratio >= self.params.big_candle_ratio and self.dataclose[i] > self.dataopen[i]:
                        # 记录大阳线收盘价下方50%的位置作为底部价格
                        bottom_price = self.dataclose[i] * 0.5
                        bottoms.append(bottom_price)
                        self.log(f'POTENTIAL BOTTOM AT {i}: Close={self.dataclose[i]:.2f}, Bottom={bottom_price:.2f}, Ratio={candle_ratio:.2%}')
            except IndexError:
                continue
        
        if bottoms:
            return min(bottoms)  # 返回最低的底部价格
        return None

    def next(self):
        self.log(f'Close, {self.dataclose[0]:.2f}')
        
        if self.order:
            return
        
        # 寻找底部
        current_bottom = self.find_bottoms()
        
        # 更新最低底部价格
        if current_bottom:
            if self.bottom_price is None or current_bottom < self.bottom_price:
                self.bottom_price = current_bottom
                self.log(f'NEW BOTTOM FOUND: {self.bottom_price:.2f}')
        
        # 买入逻辑
        if self.bottom_price and not self.bought:
            buy_range_low = self.bottom_price * (1 - self.params.buy_range)
            buy_range_high = self.bottom_price * (1 + self.params.buy_range)
            
            if buy_range_low <= self.dataclose[0] <= buy_range_high:
                self.log(f'BUY CREATE, Price: {self.dataclose[0]:.2f}, Amount: {self.params.buy_amount:.2f}')
                self.order = self.buy(value=self.params.buy_amount)  # 每次买入固定金额
        
        # 卖出逻辑
        if self.bought:
            # 目标盈利卖出
            if self.target_sell_price and self.dataclose[0] >= self.target_sell_price:
                self.log(f'SELL CREATE, Price: {self.dataclose[0]:.2f}, Target Reached')
                self.order = self.sell()
            # 止损卖出
            elif self.stop_loss_price and self.dataclose[0] <= self.stop_loss_price:
                self.log(f'SELL CREATE, Price: {self.dataclose[0]:.2f}, Stop Loss Triggered')
                self.order = self.sell()

# 导入现有的CSV数据加载器和回测函数
from backtrade import CSVDataLoader, run_backtest

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        stock_code = sys.argv[1]
    else:
        stock_code = '000001'  # 默认使用平安银行
    data_path = './daily_data_cache'
    
    # 运行回测
    run_backtest(stock_code, data_path, strategy_class=BottomBreakoutStrategy, params={
        'lookback_days': 30,
        'max_down_days': 3,
        'big_candle_ratio': 0.05,
        'buy_range': 0.02,
        'target_profit': 0.08
    })
