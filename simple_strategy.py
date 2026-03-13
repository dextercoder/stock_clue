import pandas as pd
import numpy as np
import datetime
import time

# 策略参数配置
STRATEGY_PARAMS = {
    'time_window': 60,  # 观察时间窗口（天）
    'min_continuous_down': 2,  # 最小连续下跌天数
    'min_daily_down': 0.003,  # 单日最小跌幅
    'min_total_down': 0.03,  # 最小累计跌幅
    'max_total_down': 0.20,  # 最大累计跌幅
    'max_box_amplitude': 0.06,  # 小箱体最大振幅
    'max_box_change': 0.03,  # 小箱体最大涨跌幅
    'min_shadow_ratio': 1.5,  # 下影线与实体最小比例
    'min_shadow_length': 0.4,  # 下影线占K线总长度的最小比例
    'buy_price_range': 0.03,  # 买入价格范围（上下3%）
    'min_rebound_up': 0.005  # 反弹阳线最小涨幅
}

# 模拟数据生成函数
def generate_simulation_data():
    # 创建日期序列
    dates = pd.date_range(start='2023-01-01', end='2023-03-31', freq='B')
    
    # 创建完全固定的数据
    data = []
    
    # 前面的K线数据，前38天（索引0-37）
    base_price = 10.0
    for i, date in enumerate(dates[:38]):
        open_price = base_price
        high = base_price * 1.01
        low = base_price * 0.99
        close_price = base_price * 1.00
        volume = 2000000
        data.append([date, open_price, high, low, close_price, volume])
        base_price = close_price
    
    # 连续下跌趋势（3天连续下跌，索引38-40）
    for i, date in enumerate(dates[38:41]):
        open_price = base_price
        high = base_price * 1.005
        low = base_price * 0.98
        close_price = base_price * 0.99
        volume = 2500000
        data.append([date, open_price, high, low, close_price, volume])
        base_price = close_price
    
    # 连续下跌后的额外一天（索引41）
    date = dates[41]
    open_price = base_price
    high = base_price * 1.005
    low = base_price * 0.995
    close_price = base_price
    volume = 2000000
    data.append([date, open_price, high, low, close_price, volume])
    
    # K1: 绿K线（阴线）且箱体大（索引42）
    date = dates[42]
    k1_open = base_price * 1.010  # 大幅高开
    k1_high = k1_open * 1.030      # 更大的箱体，确保振幅足够大
    k1_low = k1_open * 0.950       # 更大的箱体
    k1_close = k1_open * 0.970     # 阴线（收盘价 < 开盘价）
    volume = 3000000
    data.append([date, k1_open, k1_high, k1_low, k1_close, volume])
    
    # K2: 小箱体K线，有长下影线，是阳线（索引43）
    date = dates[43]
    k2_open = k1_close * 0.998     # 略微低开
    k2_high = k2_open * 1.008      # 小箱体振幅
    k2_low = k2_open * 0.930       # 长下影线
    # 确保K2收盘 < K1收盘且K2是阳线
    k2_close = k1_close * 0.995     # 确保小K线收盘 < 左边收盘价
    if k2_close <= k2_open:
        k2_close = k2_open * 1.005  # 确保K2是阳线
    volume = 2800000
    data.append([date, k2_open, k2_high, k2_low, k2_close, volume])
    
    # K3: 红K线（阳线）（索引44）
    date = dates[44]
    k3_open = k2_close * 1.015     # 高开，确保高于小K线收盘价
    k3_high = k3_open * 1.020      # 上涨
    k3_low = k3_open * 0.990       # 最低价比开盘价略低
    k3_close = k3_open * 1.015     # 阳线（收盘价 > 开盘价）
    volume = 3500000
    data.append([date, k3_open, k3_high, k3_low, k3_close, volume])
    
    # 后面的K线数据（索引44-结束）
    base_price = k3_close
    for i, date in enumerate(dates[44:], 44):
        open_price = base_price
        high = base_price * 1.01
        low = base_price * 0.99
        close_price = base_price * 1.00
        volume = 2200000
        data.append([date, open_price, high, low, close_price, volume])
        base_price = close_price
    
    # 创建DataFrame
    df = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    df.set_index('date', inplace=True)
    
    # 打印精确的K线数据用于调试
    print("\n精确生成的倒三角形态K线数据:")
    print(f"K1 (索引41): open={k1_open:.2f}, high={k1_high:.2f}, low={k1_low:.2f}, close={k1_close:.2f}")
    print(f"  K1是阴线: {k1_close < k1_open}")
    print(f"  K1振幅: {(k1_high - k1_low)/k1_open:.4f}")
    
    print(f"K2 (索引42): open={k2_open:.2f}, high={k2_high:.2f}, low={k2_low:.2f}, close={k2_close:.2f}")
    print(f"  K2是阳线: {k2_close > k2_open}")
    print(f"  K2振幅: {(k2_high - k2_low)/k2_open:.4f}")
    print(f"  K2收盘 < K1收盘: {k2_close < k1_close}")
    print(f"  K2下影线: {k2_open - k2_low:.2f}")
    print(f"  K2实体: {k2_close - k2_open:.2f}")
    print(f"  K2下影线/实体比例: {(k2_open - k2_low)/(k2_close - k2_open):.2f}")
    
    print(f"K3 (索引43): open={k3_open:.2f}, high={k3_high:.2f}, low={k3_low:.2f}, close={k3_close:.2f}")
    print(f"  K3是阳线: {k3_close > k3_open}")
    print(f"  K2收盘 < K3开盘: {k2_close < k3_open}")
    
    return df

# K线形态判断函数
def is_yin_line(open_price, close_price):
    return close_price < open_price

def is_yang_line(open_price, close_price):
    return close_price > open_price

def is_small_box(open_price, high, low, close_price):
    amplitude = (high - low) / open_price
    change = abs(close_price - open_price) / open_price
    return amplitude < STRATEGY_PARAMS['max_box_amplitude'] and change < STRATEGY_PARAMS['max_box_change']

def has_long_shadow(open_price, high, low, close_price):
    """判断是否有长下影线（进一步放宽条件）"""
    body_length = abs(close_price - open_price)
    shadow_length = open_price - low if close_price > open_price else close_price - low
    total_length = high - low
    
    if total_length == 0:
        return False
        
    # 放宽条件：下影线只要比实体长即可
    ratio = shadow_length / body_length if body_length != 0 else 100
    length_pct = shadow_length / total_length
    
    return ratio > 1.2 and length_pct > 0.3

# 调整倒三角形态判断
def is_triangle_shape(k1, k2, k3):
    """判断是否为倒三角形态（放宽条件）"""
    # 只要求第2根K线的最低价是三根中的最低
    return k2['low'] < k1['low'] and k2['low'] < k3['low']
# 连续下跌趋势判断函数
def has_continuous_down_trend(df, window=None):
    if window is None:
        window = STRATEGY_PARAMS['time_window']
    
    recent_df = df.tail(window).copy()
    if len(recent_df) < window:
        return False, []
    
    recent_df['pct_change'] = recent_df['close'].pct_change()
    
    max_continuous_down = 0
    current_continuous_down = 0
    total_down = 0
    found_dates = []
    
    for i in range(1, len(recent_df)):
        date = recent_df.index[i]
        change = recent_df['pct_change'].iloc[i]
        
        if change < -STRATEGY_PARAMS['min_daily_down']:
            current_continuous_down += 1
            total_down += abs(change)
            found_dates.append(date)
        else:
            if current_continuous_down >= STRATEGY_PARAMS['min_continuous_down'] and \
               STRATEGY_PARAMS['min_total_down'] <= total_down <= STRATEGY_PARAMS['max_total_down']:
                return True, found_dates
            
            current_continuous_down = 0
            total_down = 0
            found_dates = []
    
    if current_continuous_down >= STRATEGY_PARAMS['min_continuous_down'] and \
       STRATEGY_PARAMS['min_total_down'] <= total_down <= STRATEGY_PARAMS['max_total_down']:
        return True, found_dates
    
    return False, []

# 倒三角形态识别函数
def find_triangle_bottom(df):
    has_down, down_dates = has_continuous_down_trend(df)
    if not has_down:
        print("DEBUG: 没有连续下跌趋势")
        return False, None, None, None
    
    print(f"DEBUG: 连续下跌日期: {[d.date() for d in down_dates]}")
    
    down_end_idx = df.index.get_loc(down_dates[-1])
    print(f"DEBUG: 连续下跌结束索引: {down_end_idx}")
    
    if down_end_idx + 3 >= len(df):
        print(f"DEBUG: 后续K线不足 - 当前索引: {down_end_idx}, 总长度: {len(df)}")
        return False, None, None, None
    
    k1_idx = down_end_idx + 1
    k2_idx = down_end_idx + 2
    k3_idx = down_end_idx + 3
    
    print(f"DEBUG: K线索引 - k1: {k1_idx}, k2: {k2_idx}, k3: {k3_idx}")
    
    # 获取原始K线
    k1 = df.iloc[k1_idx]
    k2 = df.iloc[k2_idx]
    k3 = df.iloc[k3_idx]
    
    print(f"DEBUG: 原始K1 ({k1.name.date()}) - 开盘: {k1['open']:.2f}, 最高: {k1['high']:.2f}, 最低: {k1['low']:.2f}, 收盘: {k1['close']:.2f}")
    print(f"DEBUG: 原始K2 ({k2.name.date()}) - 开盘: {k2['open']:.2f}, 最高: {k2['high']:.2f}, 最低: {k2['low']:.2f}, 收盘: {k2['close']:.2f}")
    print(f"DEBUG: 原始K3 ({k3.name.date()}) - 开盘: {k3['open']:.2f}, 最高: {k3['high']:.2f}, 最低: {k3['low']:.2f}, 收盘: {k3['close']:.2f}")
    
    # 检查原始K线是否符合倒三角形态
    # 检查左边是绿K线（阴线）
    is_left_green = is_yin_line(k1['open'], k1['close'])
    
    # 检查右边是红K线（阳线）
    is_right_red = is_yang_line(k3['open'], k3['close'])
    
    # 检查小K线是阳线
    is_small_yang = is_yang_line(k2['open'], k2['close'])
    
    # 检查小K线有长下影线
    has_long_shadow_k2 = has_long_shadow(k2['open'], k2['high'], k2['low'], k2['close'])
    
    # 检查小K线是小箱体
    is_small_box_k2 = is_small_box(k2['open'], k2['high'], k2['low'], k2['close'])
    
    # 检查小K线的收盘价比左边阴线的收盘价低
    is_small_close_lower_left = k2['close'] < k1['close']
    
    # 检查小K线的收盘价比右边阳线的开盘价低
    is_small_close_lower_right = k2['close'] < k3['open']
    
    # 检查左边箱体大（振幅 > 小箱体振幅）
    left_amplitude = (k1['high'] - k1['low']) / k1['open']
    is_left_big_box = left_amplitude > STRATEGY_PARAMS['max_box_amplitude']
    
    # 组合所有条件
    is_triangle = is_left_green and is_right_red and is_small_yang and has_long_shadow_k2 and \
                 is_small_box_k2 and is_small_close_lower_left and is_small_close_lower_right and is_left_big_box
    
    print(f"DEBUG: 倒三角形态检查结果: {is_triangle}")
    print(f"  左边是绿K线: {is_left_green}")
    print(f"  右边是红K线: {is_right_red}")
    print(f"  小K线是阳线: {is_small_yang}")
    print(f"  小K线有长下影线: {has_long_shadow_k2}")
    print(f"  小K线是小箱体: {is_small_box_k2}")
    print(f"  小K线收盘 < 左边收盘: {is_small_close_lower_left} ({k2['close']:.2f} < {k1['close']:.2f})")
    print(f"  小K线收盘 < 右边开盘: {is_small_close_lower_right} ({k2['close']:.2f} < {k3['open']:.2f})")
    print(f"  左边箱体大: {is_left_big_box} (振幅: {left_amplitude:.4f})")
    
    if not is_triangle:
        print("DEBUG: 未识别到倒三角形态")
        return False, None, None, None
    
    print("DEBUG: 找到倒三角形态！")
    return True, k1, k2, k3

# 主测试函数
def test_strategy():
    print("倒三角底部识别策略测试")
    
    # 生成模拟数据
    df = generate_simulation_data()
    
    # 测试连续下跌趋势判断
    has_down, down_dates = has_continuous_down_trend(df)
    print(f"连续下跌趋势: {has_down}")
    if has_down:
        print(f"连续下跌日期: {[d.date() for d in down_dates]}")
    
    # 测试倒三角形态识别
    has_triangle, k1, k2, k3 = find_triangle_bottom(df)
    if has_triangle:
        print(f"找到倒三角形态!")
        print(f"K1: {k1.name.date()}, K2: {k2.name.date()}, K3: {k3.name.date()}")
    else:
        print(f"未识别到倒三角形态")

# 运行测试
if __name__ == "__main__":
    test_strategy()