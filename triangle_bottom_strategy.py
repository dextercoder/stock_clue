import pandas as pd
import numpy as np
import datetime
from utils import get_stock_info, get_daily
import time

# 策略参数配置
STRATEGY_PARAMS = {
    'time_window': 60,  # 观察时间窗口（天）
    'min_continuous_down': 3,  # 最小连续下跌天数
    'min_daily_down': 0.005,  # 单日最小跌幅
    'min_total_down': 0.05,  # 最小累计跌幅
    'max_total_down': 0.15,  # 最大累计跌幅
    'max_box_amplitude': 0.04,  # 小箱体最大振幅
    'max_box_change': 0.02,  # 小箱体最大涨跌幅
    'min_shadow_ratio': 2,  # 下影线与实体最小比例
    'min_shadow_length': 0.5,  # 下影线占K线总长度的最小比例
    'buy_price_range': 0.02,  # 买入价格范围（上下2%）
    'min_rebound_up': 0.01  # 反弹阳线最小涨幅
}

# ---------------------- K线形态判断函数 ----------------------
def is_yin_line(open_price, close_price):
    """判断是否为阴线"""
    return close_price < open_price

def is_yang_line(open_price, close_price):
    """判断是否为阳线"""
    return close_price > open_price

def is_small_box(open_price, high, low, close_price):
    """判断是否为小箱体K线"""
    amplitude = (high - low) / open_price
    change = abs(close_price - open_price) / open_price
    return amplitude < STRATEGY_PARAMS['max_box_amplitude'] and change < STRATEGY_PARAMS['max_box_change']

def has_long_shadow(open_price, high, low, close_price):
    """判断是否有长下影线"""
    # 计算实体长度
    body_length = abs(close_price - open_price)
    
    # 计算下影线长度
    if close_price > open_price:
        shadow_length = open_price - low
    else:
        shadow_length = close_price - low
    
    # 计算K线总长度
    total_length = high - low
    
    # 条件：下影线长度 > 实体长度的N倍，且下影线占K线总长度的比例 > M
    return shadow_length > body_length * STRATEGY_PARAMS['min_shadow_ratio'] and \
           shadow_length / total_length > STRATEGY_PARAMS['min_shadow_length']

# ---------------------- 连续下跌趋势判断函数 ----------------------
def has_continuous_down_trend(df, window=None):
    """判断是否存在连续下跌趋势"""
    if window is None:
        window = STRATEGY_PARAMS['time_window']
    
    # 获取最近N天的数据
    recent_df = df.tail(window).copy()
    if len(recent_df) < window:
        print(f"DEBUG: 数据不足{window}天")
        return False, []
    
    # 计算每日涨跌幅
    recent_df['pct_change'] = recent_df['close'].pct_change()
    
    # 寻找连续下跌的序列
    max_continuous_down = 0
    current_continuous_down = 0
    total_down = 0
    found_dates = []
    
    print(f"DEBUG: 检查最近 {len(recent_df)} 天的数据")
    
    for i in range(1, len(recent_df)):
        date = recent_df.index[i]
        change = recent_df['pct_change'].iloc[i]
        
        if change < -STRATEGY_PARAMS['min_daily_down']:
            current_continuous_down += 1
            total_down += abs(change)
            found_dates.append(date)
            print(f"DEBUG: {date.date()} - 跌幅: {change:.4f}, 连续: {current_continuous_down}天, 累计跌幅: {total_down:.4f}")
        else:
            # 检查当前连续下跌是否符合条件
            if current_continuous_down >= STRATEGY_PARAMS['min_continuous_down'] and \
               STRATEGY_PARAMS['min_total_down'] <= total_down <= STRATEGY_PARAMS['max_total_down']:
                print(f"DEBUG: 找到符合条件的连续下跌 - 天数: {current_continuous_down}, 累计跌幅: {total_down:.4f}")
                return True, found_dates
            
            # 重置计数器
            if current_continuous_down > 0:
                print(f"DEBUG: 连续下跌中断 - 累计{current_continuous_down}天, 累计跌幅{total_down:.4f}")
            current_continuous_down = 0
            total_down = 0
            found_dates = []
    
    # 检查最后一个连续下跌序列
    if current_continuous_down >= STRATEGY_PARAMS['min_continuous_down'] and \
       STRATEGY_PARAMS['min_total_down'] <= total_down <= STRATEGY_PARAMS['max_total_down']:
        print(f"DEBUG: 找到符合条件的连续下跌(末尾) - 天数: {current_continuous_down}, 累计跌幅: {total_down:.4f}")
        return True, found_dates
    
    print(f"DEBUG: 未找到符合条件的连续下跌 - 最大连续天数: {max_continuous_down}, 最大累计跌幅: {total_down:.4f}")
    return False, []

# ---------------------- 倒三角形态识别函数 ----------------------
def find_triangle_bottom(df):
    """识别倒三角底部形态"""
    # 检查是否存在连续下跌趋势
    has_down, down_dates = has_continuous_down_trend(df)
    if not has_down:
        return False, None, None, None
    
    # 获取连续下跌后的索引位置
    down_end_idx = df.index.get_loc(down_dates[-1])
    
    # 检查是否有足够的后续K线进行分析（至少3根）
    if down_end_idx + 3 >= len(df):
        return False, None, None, None
    
    # 获取关键3根K线
    k1_idx = down_end_idx + 1  # 第1根：下跌阴线
    k2_idx = down_end_idx + 2  # 第2根：带长下影线的小箱体K线
    k3_idx = down_end_idx + 3  # 第3根：反弹阳线
    
    k1 = df.iloc[k1_idx]
    k2 = df.iloc[k2_idx]
    k3 = df.iloc[k3_idx]
    
    # 检查第1根K线：下跌阴线
    if not is_yin_line(k1['open'], k1['close']):
        return False, None, None, None
    
    # 检查第2根K线：带长下影线的小箱体K线
    if not is_small_box(k2['open'], k2['high'], k2['low'], k2['close']):
        return False, None, None, None
    
    if not has_long_shadow(k2['open'], k2['high'], k2['low'], k2['close']):
        return False, None, None, None
    
    # 检查第3根K线：反弹阳线
    if not is_yang_line(k3['open'], k3['close']):
        return False, None, None, None
    
    if (k3['close'] - k3['open']) / k3['open'] < STRATEGY_PARAMS['min_rebound_up']:
        return False, None, None, None
    
    # 检查倒三角形态（第2根K线处于下方）
    if k2['high'] >= k1['low'] or k2['high'] >= k3['low']:
        return False, None, None, None
    
    return True, k1, k2, k3

# ---------------------- 买入信号判断函数 ----------------------
def check_buy_signal(df, k2):
    """检查是否满足买入信号"""
    if k2 is None:
        return False, None
    
    # 获取当前价格（最近收盘价）
    current_price = df['close'].iloc[-1]
    
    # 计算买入价格范围
    buy_low = k2['low'] * (1 - STRATEGY_PARAMS['buy_price_range'])
    buy_high = k2['high'] * (1 + STRATEGY_PARAMS['buy_price_range'])
    
    # 检查当前价格是否在范围内
    is_in_range = buy_low <= current_price <= buy_high
    
    # 另一种判断方式：当前价格低于小K线最高价且高于小K线最低价
    is_in_box = k2['low'] <= current_price <= k2['high']
    
    return is_in_range or is_in_box, current_price

# ---------------------- 主策略函数 ----------------------
def run_strategy(symbol=None):
    """运行倒三角底部策略"""
    print("\n" + "="*60)
    print("倒三角底部识别策略开始运行...")
    print("="*60)
    
    # 获取股票列表
    if symbol:
        # 单个股票测试
        stock_list = pd.DataFrame({'code': [symbol], 'name': ['测试股票']})
    else:
        # 全部股票扫描
        stock_list = get_stock_info()
    
    print(f"\n待分析股票数量: {len(stock_list)}")
    
    stock_list = stock_list[0:3000]
    # 结果列表
    results = []
    
    # 遍历股票
    for index, row in stock_list.iterrows():
        code = row['code']
        name = row['name']
        
        print(f"\n{index+1}/{len(stock_list)} 分析股票: {code} {name}")
        
        try:
            # 获取日线数据
            df = get_daily(code)
            
            if df is None or len(df) < STRATEGY_PARAMS['time_window']:
                print(f"  数据不足，跳过")
                continue
            
            # 识别倒三角形态
            has_triangle, k1, k2, k3 = find_triangle_bottom(df)
            
            if not has_triangle:
                print(f"  未发现倒三角形态")
                continue
            
            print(f"  发现倒三角形态:")
            print(f"    第1根阴线日期: {k1.name.date()}, 价格: {k1['close']:.2f}")
            print(f"    第2根小箱体日期: {k2.name.date()}, 最低价: {k2['low']:.2f}, 最高价: {k2['high']:.2f}")
            print(f"    第3根阳线日期: {k3.name.date()}, 价格: {k3['close']:.2f}")
            
            # 检查买入信号
            is_buy, current_price = check_buy_signal(df, k2)
            
            if is_buy:
                print(f"  ✅ 触发买入信号: 当前价格 {current_price:.2f} 接近小箱体价格范围")
                
                # 记录结果
                results.append({
                    'code': code,
                    'name': name,
                    'current_price': current_price,
                    'box_low': k2['low'],
                    'box_high': k2['high'],
                    'triangle_date': k2.name.date(),
                    'buy_signal': True
                })
            else:
                print(f"  未触发买入信号: 当前价格 {current_price:.2f} 不在小箱体价格范围")
                
        except Exception as e:
            print(f"  分析失败: {str(e)}")
            time.sleep(1)  # 防止API调用过于频繁
    
    # 输出结果统计
    print("\n" + "="*60)
    print(f"策略运行完成")
    print(f"总分析股票数: {len(stock_list)}")
    print(f"发现倒三角形态股票数: {len(results)}")
    print(f"触发买入信号股票数: {sum(1 for r in results if r['buy_signal'])}")
    print("="*60)
    
    # 输出详细结果
    if results:
        print("\n触发买入信号的股票列表:")
        print("-"*80)
        print(f"{'代码':<8} {'名称':<10} {'当前价格':<10} {'小箱体范围':<20} {'形态日期':<12} {'状态':<8}")
        print("-"*80)
        
        for result in results:
            if result['buy_signal']:
                box_range = f"{result['box_low']:.2f}~{result['box_high']:.2f}"
                status = "买入"
                print(f"{result['code']:<8} {result['name']:<10} {result['current_price']:<10.2f} {box_range:<20} {str(result['triangle_date']):<12} {status:<8}")
    
    return results

# ---------------------- 测试函数 ----------------------
def test_with_debug(symbol="000001"):
    """带调试信息的测试函数"""
    print("\n" + "="*60)
    print(f"调试模式：分析股票 {symbol}")
    print("="*60)
    
    # 导入必要的模块
    import traceback
    
    try:
        # 获取日线数据
        df = get_daily(symbol)
        
        if df is None or len(df) < STRATEGY_PARAMS['time_window']:
            print(f"数据不足，跳过")
            return False
        
        print(f"获取到 {len(df)} 条数据")
        
        # 识别倒三角形态
        has_triangle, k1, k2, k3 = find_triangle_bottom(df)
        
        if not has_triangle:
            print("未发现倒三角形态")
            return False
        
        print(f"发现倒三角形态:")
        print(f"  第1根阴线日期: {k1.name.date()}, 价格: {k1['close']:.2f}")
        print(f"  第2根小箱体日期: {k2.name.date()}, 最低价: {k2['low']:.2f}, 最高价: {k2['high']:.2f}")
        print(f"  第3根阳线日期: {k3.name.date()}, 价格: {k3['close']:.2f}")
        
        # 检查买入信号
        is_buy, current_price = check_buy_signal(df, k2)
        
        if is_buy:
            print(f"✅ 触发买入信号: 当前价格 {current_price:.2f} 接近小箱体价格范围")
            return True
        else:
            print(f"未触发买入信号: 当前价格 {current_price:.2f} 不在小箱体价格范围")
            return False
            
    except Exception as e:
        print(f"分析失败: {str(e)}")
        traceback.print_exc()
        return False

# ---------------------- 主函数 ----------------------
if __name__ == "__main__":
    # 单个股票调试测试
    test_with_debug(symbol="000001")
    
    # 注释掉全部股票扫描
    # run_strategy()
