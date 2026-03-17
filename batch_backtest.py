#!/usr/bin/env python3
import os
import argparse
import backtrader as bt
import pandas as pd

# 导入策略类和数据加载器
from backtrade import SimpleMA, BottomBreakoutStrategy, CSVDataLoader

# 获取daily_data_cache目录下的所有CSV文件
def get_all_stock_codes(data_dir='./daily_data_cache'):
    stock_codes = []
    if not os.path.exists(data_dir):
        print(f"Directory {data_dir} not found")
        return stock_codes
    
    for filename in os.listdir(data_dir):
        if filename.endswith('_daily.csv'):
            stock_code = filename.replace('_daily.csv', '')
            stock_codes.append(stock_code)
    
    return stock_codes

# 运行批量回测函数
# 使用同一个cerebro实例处理所有股票
def run_batch_backtest(stock_codes, strategy_class, strategy_params, cash, data_dir):
    cerebro = bt.Cerebro()
    
    # 添加策略
    cerebro.addstrategy(strategy_class, **strategy_params)
    
    # 为每只股票加载数据并添加到cerebro
    for stock_code in stock_codes:
        try:
            data = CSVDataLoader.load_data(stock_code, data_dir)
            cerebro.adddata(data, name=stock_code)
            print(f"Added data for {stock_code}")
        except Exception as e:
            print(f"Error loading data for {stock_code}: {e}")
    
    # 设置总资金
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=0.001)
    
    # 运行回测
    print(f"\n" + "="*50)
    print(f"Running batch backtest with {len(stock_codes)} stocks")
    print(f"Initial Portfolio Value: {cash:.2f}")
    print("="*50)
    
    cerebro.run()
    
    # 获取最终资金
    final_value = cerebro.broker.getvalue()
    print(f"Final Portfolio Value: {final_value:.2f}")
    print(f"Total Profit: {final_value - cash:.2f}")
    if cash > 0:
        print(f"Total Profit Rate: {((final_value - cash) / cash) * 100:.2f}%")
    print("="*50)
    
    return cash, final_value

# 主函数
def main():
    parser = argparse.ArgumentParser(description='Batch Backtesting Tool')
    parser.add_argument('--strategy', default='bottombreakout', choices=['simplema', 'bottombreakout'], 
                        help='Strategy to use (default: bottombreakout)')
    parser.add_argument('--data', default='./daily_data_cache', help='Path to data directory')
    parser.add_argument('--cash', type=float, default=100000.0, help='Total initial cash (default: 100000.0)')
    parser.add_argument('--limit', type=int, default=None, help='Limit the number of stocks to test')
    
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
    
    # 获取所有股票代码
    stock_codes = get_all_stock_codes(args.data)
    
    if not stock_codes:
        print("No stock data files found")
        return
    
    print(f"Found {len(stock_codes)} stock codes")
    
    # 限制测试数量（如果有指定）
    if args.limit:
        stock_codes = stock_codes[:args.limit]
        print(f"Testing first {args.limit} stocks")
    
    # 选择策略类
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
    
    # 运行批量回测，使用总资金池
    total_initial_value, total_final_value = run_batch_backtest(
        stock_codes, 
        strategy_class, 
        strategy_params, 
        args.cash, 
        args.data
    )
    
    # 输出统计信息
    print(f"\n" + "="*50)
    print(f"Batch Backtest Summary")
    print("="*50)
    print(f"Total stocks: {len(stock_codes)}")
    print("-"*50)
    print(f"Total Initial Portfolio Value: {total_initial_value:.2f}")
    print(f"Total Final Portfolio Value: {total_final_value:.2f}")
    print(f"Total Profit: {total_final_value - total_initial_value:.2f}")
    if total_initial_value > 0:
        print(f"Total Profit Rate: {((total_final_value - total_initial_value) / total_initial_value) * 100:.2f}%")
    print("="*50)

if __name__ == '__main__':
    main()