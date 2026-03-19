import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc
import utils
# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def get_stock_name_mapping():
    """
    从指定的Excel文件加载股票名称映射
    返回：字典，键为股票代码，值为股票名称
    """
    excel_path = 'all_stocks_name/A股所有股票代码列表.xlsx'
    try:
        df = pd.read_excel(excel_path)
        # 创建股票代码到股票名称的映射字典，确保股票代码是6位格式（补前导零）
        df['股票代码_str'] = df['股票代码'].astype(int).astype(str).str.zfill(6)
        stock_map = dict(zip(df['股票代码_str'], df['股票名称']))
        print(f"从Excel文件加载了 {len(stock_map)} 只股票的名称映射")
        return stock_map
    except Exception as e:
        print(f"加载股票名称映射时出错: {str(e)}")
        return {}


class BigCandlePullbackAnalyzer:
    def __init__(self, data_path, lookback_days=60, big_candle_ratio=0.05, pullback_threshold=0.02):
        self.data_path = data_path
        self.lookback_days = lookback_days  # 回溯天数
        self.big_candle_ratio = big_candle_ratio  # 大阳线的最小涨幅比例
        self.pullback_threshold = pullback_threshold  # 回调到阳线底部的阈值
        self.matching_stocks = []
        
        # 加载股票名称映射
        self.stock_name_map = get_stock_name_mapping()
        print(f"已加载 {len(self.stock_name_map)} 只股票的名称映射")
    
    def load_stock_data(self, stock_file):
        """加载单个股票数据"""
        file_path = os.path.join(self.data_path, stock_file)
        df = pd.read_csv(file_path)
        df['date'] = pd.to_datetime(df['date'])
        df.sort_values('date', inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
    
    def get_weekly_data(self, df):
        """将日线数据转换为周线数据"""
        # 设置日期为索引
        df.set_index('date', inplace=True)
        
        # 按周聚合数据
        weekly_data = df.resample('W').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        # 重置索引
        weekly_data.reset_index(inplace=True)
        return weekly_data
    
    def is_weekly_uptrend(self, weekly_data, lookback_weeks=8):
        """判断周线是否处于上升趋势"""
        if len(weekly_data) < lookback_weeks:
            return False
        
        # 获取最近几周的数据
        recent_weekly = weekly_data.tail(lookback_weeks)
        
        # 条件1: 中长期趋势判断（最近8周）
        close_prices = recent_weekly['close'].values
        # 最近收盘价高于8周前的收盘价
        if close_prices[-1] <= close_prices[0]:
            return False
        
        # 条件2: 计算周线MA8
        if len(weekly_data) >= 8:
            weekly_data['MA8'] = weekly_data['close'].rolling(window=8).mean()
            
            # 最近MA8呈上升趋势（至少最近2周）
            if len(weekly_data) >= 2:
                if weekly_data['MA8'].iloc[-1] <= weekly_data['MA8'].iloc[-2]:
                    return False
        
        # 条件3: 最近5周的趋势判断
        recent_5weeks = recent_weekly.tail(5)
        recent_5weeks_close = recent_5weeks['close'].values
        
        # 最近5周收盘价整体呈上升趋势
        if recent_5weeks_close[-1] <= recent_5weeks_close[0]:
            return False
        
        # 最近5周内至少有2周收盘价上升
        up_weeks = sum(1 for i in range(1, len(recent_5weeks_close)) if recent_5weeks_close[i] > recent_5weeks_close[i-1])
        if up_weeks < 2:
            return False
        
        # 条件4: 最近3周的高点和低点判断
        recent_3weeks = recent_weekly.tail(3)
        recent_3weeks_highs = recent_3weeks['high'].values
        recent_3weeks_lows = recent_3weeks['low'].values
        
        # 最近3周高点呈上升趋势
        if not (recent_3weeks_highs[-1] > recent_3weeks_highs[0]):
            return False
        
        # 最近3周低点呈上升趋势
        if not (recent_3weeks_lows[-1] > recent_3weeks_lows[0]):
            return False
        
        return True
    
    def find_big_candle_with_pullback(self, df, stock_code=None):
        """查找大阳线后回调到阳线底部的模式
        
        参数:
            df: 股票日线数据
            stock_code: 股票代码（可选，如果传入则优先使用）
            
        返回:
            匹配的模式信息或None
        """
        if len(df) < self.lookback_days:  # 至少需要lookback_days天的数据
            return None
        
        # 检查周线是否处于上升趋势
        try:
            # 创建日线数据的副本以避免修改原始数据
            df_copy = df.copy()
            # 生成周线数据
            weekly_data = self.get_weekly_data(df_copy)
            # 判断周线趋势
            if not self.is_weekly_uptrend(weekly_data):
                return None
        except Exception as e:
            print(f"周线趋势判断出错: {str(e)}")
            return None
        
        # 获取最近一段时间的数据
        recent_data = df.tail(self.lookback_days).copy()
        
        # 查找大阳线
        big_candle_candidates = []
        
        for i in range(len(recent_data) - 1):
            current_day = recent_data.iloc[i]
            # 计算当日涨跌幅
            day_change = (current_day['close'] - current_day['open']) / current_day['open']
            
            # 条件1: 是大阳线
            if day_change >= self.big_candle_ratio:
                # 条件2: 大阳线的实体较大（至少占全天波动的60%）
                day_range = current_day['high'] - current_day['low']
                if day_range > 0:
                    body_ratio = abs(current_day['close'] - current_day['open']) / day_range
                    if body_ratio >= 0.6:
                        big_candle_candidates.append((i, current_day, day_change))
        
        if not big_candle_candidates:
            return None
        
        # 计算所有大阳线的底部价格，并找到最低的那个
        big_candle_bottoms = []
        for idx, candle, change in big_candle_candidates:
            bottom = min(candle['open'], candle['close'])
            big_candle_bottoms.append((idx, candle, change, bottom))
        
        # 按底部价格从低到高排序，取最低的大阳线
        big_candle_bottoms.sort(key=lambda x: x[3])
        min_bottom_idx, min_bottom_candle, min_bottom_change, min_bottom_price = big_candle_bottoms[0]
        
        # 计算最低大阳线的顶部价格
        min_bottom_top = max(min_bottom_candle['open'], min_bottom_candle['close'])
        
        # 获取最低大阳线之后的数据
        after_min_bottom = recent_data.iloc[min_bottom_idx + 1:]
        
        if len(after_min_bottom) == 0:
            return None
        
        # 检查是否回调到最低大阳线底部
        # 计算最近收盘价与最低大阳线底部的差距
        latest_close = recent_data.iloc[-1]['close']
        pullback_ratio = (latest_close - min_bottom_price) / min_bottom_price
        
        # 条件3: 最近收盘价接近最低大阳线底部（在阈值范围内）
        if not (-self.pullback_threshold <= pullback_ratio <= self.pullback_threshold):
            return None
        
        # 条件4: 回调过程中没有跌破最低大阳线底部过多
        min_after_close = after_min_bottom['close'].min()
        max_drawdown = (min_after_close - min_bottom_price) / min_bottom_price
        if max_drawdown < -0.05:  # 最大回调不超过5%
            return None
        
        # 获取股票代码和名称
        if stock_code is None:
            stock_code = recent_data['code'].iloc[0] if 'code' in recent_data.columns else 'unknown'
        # 确保股票代码是纯数字（去除可能的后缀）
        stock_code = stock_code.split('_')[0].strip()
        stock_name = self.stock_name_map.get(stock_code, stock_code)
        
        pattern_info = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'big_candle_date': min_bottom_candle['date'],
            'big_candle_open': min_bottom_candle['open'],
            'big_candle_high': min_bottom_candle['high'],
            'big_candle_low': min_bottom_candle['low'],
            'big_candle_close': min_bottom_candle['close'],
            'big_candle_change': min_bottom_change,
            'big_candle_bottom': min_bottom_price,
            'big_candle_top': min_bottom_top,
            'latest_date': recent_data.iloc[-1]['date'],
            'latest_close': latest_close,
            'pullback_ratio': pullback_ratio,
            'max_drawdown': max_drawdown,
            'total_big_candles': len(big_candle_candidates)  # 记录找到的大阳线数量
        }
        return pattern_info
    
    def analyze_all_stocks(self):
        """分析所有股票"""
        stock_files = [f for f in os.listdir(self.data_path) if f.endswith('.csv')]
        print(f"开始分析 {len(stock_files)} 只股票...")
        
        for i, stock_file in enumerate(stock_files):
            if i % 100 == 0:
                print(f"已分析 {i}/{len(stock_files)} 只股票")
            
            try:
                # 提取股票代码（先移除.csv后缀，再处理下划线）
                stock_code = os.path.splitext(stock_file)[0].split('_')[0]
                
                # 加载数据
                df = self.load_stock_data(stock_file)
                df['code'] = stock_code  # 添加股票代码列到df中
                
                # 查找符合条件的模式
                pattern_info = self.find_big_candle_with_pullback(df, stock_code=stock_code)
                if pattern_info:
                        print(f"找到匹配模式的股票: {pattern_info['stock_name']} ({pattern_info['stock_code']})")
                        print(f"  过去60天内大阳线数量: {pattern_info['total_big_candles']}")
                        print(f"  最低大阳线日期: {pattern_info['big_candle_date'].strftime('%Y-%m-%d')}")
                        print(f"  最低大阳线涨幅: {pattern_info['big_candle_change']:.2%}")
                        print(f"  最低大阳线底部: {pattern_info['big_candle_bottom']:.2f}")
                        print(f"  最新收盘价: {pattern_info['latest_close']:.2f}")
                        print(f"  回调比例: {pattern_info['pullback_ratio']:.2%}")
                        print()
                        self.matching_stocks.append((df, pattern_info))
            
            except Exception as e:
                print(f"分析股票 {stock_file} 时出错: {str(e)}")
        
        print(f"分析完成，共找到 {len(self.matching_stocks)} 只符合条件的股票")
    
    def plot_kline_with_markers(self, df, pattern_info, save_path):
        """绘制K线图并标记大阳线和回调位置"""
        # 获取最近4个月（约120天）的数据用于绘图
        plot_data = df.tail(120).copy()
        
        # 转换日期为matplotlib格式
        plot_data['date_num'] = mdates.date2num(plot_data['date'])
    
        # 创建OHLC数据格式
        ohlc_data = plot_data[['date_num', 'open', 'high', 'low', 'close']].values
        
        # 创建图形
        fig, ax = plt.subplots(figsize=(12, 6))
    
        # 绘制K线图
        candlestick_ohlc(ax, ohlc_data, width=0.6, colorup='red', colordown='green')
        
        # 设置日期格式
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()
        
        # 标记大阳线
        big_candle_date_num = mdates.date2num(pattern_info['big_candle_date'])
        big_candle_bottom = pattern_info['big_candle_bottom']
        big_candle_top = pattern_info['big_candle_top']
        big_candle_open = pattern_info['big_candle_open']
        big_candle_close = pattern_info['big_candle_close']
        
        # 绘制大阳线区域（更明显的标记）
        ax.axvspan(big_candle_date_num - 0.5, big_candle_date_num + 0.5, 
                   ymin=big_candle_bottom, ymax=big_candle_top, 
                   facecolor='yellow', alpha=0.4, label='大阳线')
        
        # 用红色矩形框圈出大阳线
        rect = plt.Rectangle(
            (big_candle_date_num - 0.45, big_candle_bottom), 
            0.9, 
            big_candle_top - big_candle_bottom, 
            facecolor='none', 
            edgecolor='red', 
            linewidth=2, 
            linestyle='--',
            label='大阳线标记'
        )
        ax.add_patch(rect)
        
        # 标记大阳线底部线
        ax.axhline(y=big_candle_bottom, color='blue', linestyle='--', alpha=0.7, 
                  label=f'大阳线底部: {big_candle_bottom:.2f}')
        
        # 标记最新收盘价
        latest_date_num = mdates.date2num(pattern_info['latest_date'])
        latest_close = pattern_info['latest_close']
        ax.axhline(y=latest_close, color='green', linestyle='--', alpha=0.7, 
                  label=f'最新收盘价: {latest_close:.2f}')
        
        # 在最新收盘价位置添加标记点
        ax.plot(latest_date_num, latest_close, 'o', color='green', markersize=8, 
                label='当前回调位置')
        
        # 设置标题和标签
        stock_code = pattern_info['stock_code']
        stock_name = pattern_info.get('stock_name', stock_code)
        
        # 在图表左上角添加股票名称和代码
        ax.text(0.02, 0.95, f'{stock_name} ({stock_code})', 
                transform=ax.transAxes, 
                fontsize=14, fontweight='bold', 
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
        
        # 设置主标题
        ax.set_title(f'大阳线后回调模式 - K线图\n大阳线日期: {pattern_info["big_candle_date"].strftime("%Y-%m-%d")}', fontsize=12)
        ax.set_xlabel('日期')
        ax.set_ylabel('价格')
        ax.grid(True, alpha=0.3)
        
        # 添加图例
        ax.legend(title=f'{stock_name} ({stock_code})')
        
        # 保存图像
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"图形已保存到: {save_path}")
        
        plt.close()
    
    def save_matching_stocks(self, save_file='./big_candle_pullback_stocks.csv'):
        """将匹配的股票保存到CSV文件"""
        if not self.matching_stocks:
            print("没有找到符合条件的股票，无法保存")
            return
        
        # 准备保存的数据
        save_data = []
        for df, pattern_info in self.matching_stocks:
            save_data.append({
                '股票代码': pattern_info['stock_code'],
                '股票名称': pattern_info['stock_name'],
                '过去60天大阳线数量': pattern_info['total_big_candles'],
                '最低大阳线日期': pattern_info['big_candle_date'].strftime('%Y-%m-%d'),
                '最低大阳线开盘价': pattern_info['big_candle_open'],
                '最低大阳线最高价': pattern_info['big_candle_high'],
                '最低大阳线最低价': pattern_info['big_candle_low'],
                '最低大阳线收盘价': pattern_info['big_candle_close'],
                '最低大阳线涨幅': pattern_info['big_candle_change'],
                '最低大阳线底部': pattern_info['big_candle_bottom'],
                '最低大阳线顶部': pattern_info['big_candle_top'],
                '最新日期': pattern_info['latest_date'].strftime('%Y-%m-%d'),
                '最新收盘价': pattern_info['latest_close'],
                '回调比例': pattern_info['pullback_ratio'],
                '最大回调': pattern_info['max_drawdown']
            })
        
        # 创建DataFrame并保存
        df_save = pd.DataFrame(save_data)
        df_save.to_csv(save_file, index=False, encoding='utf-8-sig')
        print(f"筛选结果已保存到: {save_file}")
        
        return df_save
        
    def plot_all_matching_stocks(self, save_dir='./big_candle_pullback_plots'):
        """绘制所有匹配股票的K线图"""
        if not self.matching_stocks:
            print("没有找到符合条件的股票")
            return
        
        # 创建保存目录
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        print(f"开始绘制 {len(self.matching_stocks)} 只股票的K线图...")
        
        for i, (df, pattern_info) in enumerate(self.matching_stocks):
            stock_code = pattern_info['stock_code']
            print(f"绘制 {stock_code} 的K线图 ({i+1}/{len(self.matching_stocks)})")
            
            # 保存图像 - 文件名包含股票代码和名称
            stock_name = pattern_info.get('stock_name', stock_code)
            # 清理股票名称中的特殊字符，确保文件名安全
            safe_stock_name = ''.join(e for e in stock_name if e.isalnum() or e in ['_', '-'])
            save_path = os.path.join(save_dir, f'{stock_code}_{safe_stock_name}_big_candle_pullback.png')
            self.plot_kline_with_markers(df, pattern_info, save_path)
        
        print(f"所有图形已保存到目录: {save_dir}")


if __name__ == "__main__":
    # 设置数据路径
    data_path = './daily_data_cache'
    # 移除已存在的目录及其内容
    import shutil
    if os.path.exists('./big_candle_pullback_plots'):
        shutil.rmtree('./big_candle_pullback_plots')
    
    # 创建分析器实例
    analyzer = BigCandlePullbackAnalyzer(
        data_path=data_path,
        lookback_days=20,               # 回溯天数
        big_candle_ratio=0.05,           # 大阳线最小涨幅5%
        pullback_threshold=0.02          # 回调到阳线底部的阈值2%
    )
    
    # 分析所有股票
    analyzer.analyze_all_stocks()
    
    # 保存筛选结果到文件
    if analyzer.matching_stocks:
        analyzer.save_matching_stocks()
        
        # 绘制匹配股票的K线图
        analyzer.plot_all_matching_stocks()
    else:
        print("没有找到符合条件的股票")
