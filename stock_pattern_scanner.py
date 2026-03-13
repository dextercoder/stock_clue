import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 设置tushare token（需要注册tushare账号获取）
ts.set_token('your_token_here')
pro = ts.pro_api()

# 定义A股股票列表（可以根据需要扩展）
STOCK_LIST = [
    '600000', '600519', '000001', '601318', '600036',
    '601888', '600276', '000858', '601166', '601628',
    '600887', '601398', '601857', '000333', '600031',
    '601288', '600030', '601601', '601899', '601988'
]

# 定义模式识别函数
def identify_pattern(df):
    """
    识别大阴线接长下影线后阳线的模式
    """
    # 计算K线相关指标
    df['open'] = df['open']
    df['close'] = df['close']
    df['high'] = df['high']
    df['low'] = df['low']
    
    # 计算实体长度
    df['body'] = abs(df['close'] - df['open'])
    
    # 计算上下影线
    df['upper_shadow'] = df.apply(lambda x: x['high'] - max(x['open'], x['close']), axis=1)
    df['lower_shadow'] = df.apply(lambda x: min(x['open'], x['close']) - x['low'], axis=1)
    
    # 计算K线类型
    df['is_bearish'] = df['close'] < df['open']
    df['is_bullish'] = df['close'] > df['open']
    
    # 大阴线：实体长度大于等于前日收盘价的3%
    df['is_large_bearish'] = df['is_bearish'] & (df['body'] / df['close'].shift(1) >= 0.03)
    
    # 长下影线：下影线长度大于等于实体长度的2倍
    df['is_long_lower_shadow'] = df['lower_shadow'] >= 2 * df['body']
    
    # 寻找模式：大阴线 -> 长下影线 -> 阳线
    pattern_stocks = []
    
    for i in range(2, len(df)):
        # 检查是否满足模式
        if (df.iloc[i-2]['is_large_bearish'] and  # 大阴线
            df.iloc[i-1]['is_long_lower_shadow'] and  # 长下影线
            df.iloc[i]['is_bullish']):  # 阳线
            pattern_stocks.append(df.iloc[i]['trade_date'])
    
    return pattern_stocks

# 主函数
def main():
    print("开始扫描股票模式...")
    
    # 计算日期范围（过去1个月）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    start_date_str = start_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')
    
    # 存储符合模式的股票
    results = {}
    
    for stock in STOCK_LIST:
        print(f"正在分析 {stock}...")
        try:
            # 下载股票数据
            df = pro.daily(ts_code=stock+'.SH' if stock.startswith('6') else stock+'.SZ', 
                          start_date=start_date_str, 
                          end_date=end_date_str)
            
            if len(df) >= 3:  # 需要至少3天的数据
                # 按日期排序（从早到晚）
                df = df.sort_values('trade_date')
                # 识别模式
                pattern_dates = identify_pattern(df)
                
                if pattern_dates:
                    results[stock] = pattern_dates
                    print(f"  ✓ {stock} 发现模式: {pattern_dates}")
                else:
                    print(f"  ✗ {stock} 未发现模式")
            else:
                print(f"  ⚠ {stock} 数据不足")
                
        except Exception as e:
            print(f"  ✗ {stock} 错误: {str(e)}")
    
    # 输出结果
    print("\n=== 扫描结果 ===")
    if results:
        print("发现符合模式的股票：")
        for stock, dates in results.items():
            print(f"{stock}: {dates}")
    else:
        print("未发现符合模式的股票")

if __name__ == "__main__":
    main()