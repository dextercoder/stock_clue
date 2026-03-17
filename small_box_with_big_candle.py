import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc
# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def get_stock_name_mapping():
    """
    从指定的Excel文件加载股票名称映射
    返回：字典，键为股票代码，值为股票名称
    """
    excel_path = '/Users/workspace/trae_source_code/stock_clue/all_stocks_name/A股所有股票代码列表.xlsx'
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

class SmallBoxBigCandleAnalyzer:
    def __init__(self, data_path, lookback_days=20, box_range_threshold=0.15, small_movement_threshold=0.02, small_movement_ratio=0.02, big_candle_ratio=0.05):
        self.data_path = data_path
        self.lookback_days = lookback_days
        self.box_range_threshold = box_range_threshold  # 箱体价格区间的最大百分比
        self.small_movement_threshold = small_movement_threshold  # 小波动K线的波动阈值
        self.small_movement_ratio = small_movement_ratio        # 小波动K线的比例要求
        self.big_candle_ratio = big_candle_ratio            # 大阳线的最小涨幅比例
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
    
    def find_small_box_with_big_candle(self, df, stock_code=None):
        """查找小箱体后出现大阳线的模式
        
        参数:
            df: 股票日线数据
            stock_code: 股票代码（可选，如果传入则优先使用）
            
        返回:
            匹配的模式信息或None
        """
        if len(df) < self.lookback_days + 1:  # 至少需要lookback_days + 1天的数据
            return None
        
        # 获取最近一段时间的数据（包括lookback_days和最后一天的大阳线）
        recent_data = df.tail(self.lookback_days + 1).copy()
        
        # 分离箱体期和最后一天
        box_period = recent_data.iloc[:-1]  # 箱体期数据
        last_day = recent_data.iloc[-1]     # 最后一天数据
        
        # 计算箱体期的价格范围（使用开盘价和收盘价）
        box_high = max(box_period['open'].max(), box_period['close'].max())
        box_low = min(box_period['open'].min(), box_period['close'].min())
        box_range = box_high - box_low
        box_mid = (box_high + box_low) / 2
        box_range_ratio = box_range / box_low
        
        # 条件1: 箱体期价格范围在阈值内
        if box_range_ratio > self.box_range_threshold:
            return None
        
        # 计算箱体期内每日涨跌幅
        box_period['daily_change'] = (box_period['close'] - box_period['open']) / box_period['open']
        box_period['daily_range'] = (box_period['high'] - box_period['low']) / box_period['low']
        
        # 条件2: 箱体期内有一定比例的K线价格波动较小（小于2%）
        small_movement_count = (box_period['daily_change'] <= self.small_movement_threshold).sum()
        small_movement_percentage = small_movement_count / len(box_period)
        if small_movement_percentage < self.small_movement_ratio:  # 至少有2%的K线波动小于2%
            return None
        
        # 条件3: 最后一天是大阳线
        last_day_change = (last_day['close'] - last_day['open']) / last_day['open']
        if last_day_change < self.big_candle_ratio:
            return None
        
        # 条件4: 大阳线突破箱体的上边界或接近上边界
        if last_day['close'] < box_high * 0.98:  # 收盘价至少达到箱体上边界的98%
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
            'box_start_date': box_period['date'].iloc[0],
            'box_end_date': box_period['date'].iloc[-1],
            'box_high': box_high,
            'box_low': box_low,
            'box_mid': box_mid,
            'box_range_ratio': box_range_ratio,
            'big_candle_date': last_day['date'],
            'big_candle_open': last_day['open'],
            'big_candle_high': last_day['high'],
            'big_candle_low': last_day['low'],
            'big_candle_close': last_day['close'],
            'big_candle_ratio': last_day_change
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
                pattern_info = self.find_small_box_with_big_candle(df, stock_code=stock_code)
                if pattern_info:
                    print(f"找到匹配模式的股票: {pattern_info['stock_name']} ({pattern_info['stock_code']})")
                    print(f"  箱体期: {pattern_info['box_start_date'].strftime('%Y-%m-%d')} 到 {pattern_info['box_end_date'].strftime('%Y-%m-%d')}")
                    print(f"  箱体价格区间: {pattern_info['box_low']:.2f} - {pattern_info['box_high']:.2f} ({pattern_info['box_range_ratio']:.2%})")
                    print(f"  大阳线日期: {pattern_info['big_candle_date'].strftime('%Y-%m-%d')}")
                    print(f"  大阳线涨幅: {pattern_info['big_candle_ratio']:.2%}")
                    print()
                    self.matching_stocks.append((df, pattern_info))
            
            except Exception as e:
                print(f"分析股票 {stock_file} 时出错: {str(e)}")
        
        print(f"分析完成，共找到 {len(self.matching_stocks)} 只符合条件的股票")
    
    def plot_kline_with_box(self, df, pattern_info, save_path):
        """绘制K线图并标记箱体和大阳线"""
        # 获取最近40天的数据用于绘图（更长的周期以便更好地展示箱体）
        plot_data = df.tail(40).copy()
        
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
        
        # 绘制箱体
        box_left = mdates.date2num(pattern_info['box_start_date'])
        box_right = mdates.date2num(pattern_info['box_end_date'])
        box_bottom = pattern_info['box_low']
        box_top = pattern_info['box_high']
        
        # 绘制箱体矩形
        rect = plt.Rectangle((box_left, box_bottom), box_right - box_left, box_top - box_bottom,
                           facecolor='blue', alpha=0.2, edgecolor='blue', linewidth=2, label=f'箱体区间 ({pattern_info["box_range_ratio"]:.2%})')
        ax.add_patch(rect)
        
        # 标记箱体中间线
        ax.axhline(y=pattern_info['box_mid'], color='purple', linestyle='--', alpha=0.7,
                  label=f'箱体中线: {pattern_info["box_mid"]:.2f}')
        
        # 标记大阳线
        big_candle_date_num = mdates.date2num(pattern_info['big_candle_date'])
        ax.axvline(x=big_candle_date_num, color='orange', linestyle='--', alpha=0.8,
                  label=f'大阳线日期')
        
        # 设置标题和标签
        stock_code = pattern_info['stock_code']
        stock_name = pattern_info.get('stock_name', stock_code)
        
        # 在图表左上角添加股票名称和代码
        ax.text(0.02, 0.95, f'{stock_name} ({stock_code})', 
                transform=ax.transAxes, 
                fontsize=14, fontweight='bold', 
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
        
        # 设置主标题
        ax.set_title(f'小箱体后大阳线模式 - K线图\n箱体期: {pattern_info["box_start_date"].strftime("%Y-%m-%d")} 到 {pattern_info["box_end_date"].strftime("%Y-%m-%d")}', fontsize=12)
        ax.set_xlabel('日期')
        ax.set_ylabel('价格')
        ax.grid(True, alpha=0.3)
        
        # 添加图例
        ax.legend(title=f'{stock_name} ({stock_code})')
        
        # 保存图像
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"图形已保存到: {save_path}")
        
        plt.close()
    
    def save_matching_stocks(self, save_file='./small_box_stocks.csv'):
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
                '箱体开始日期': pattern_info['box_start_date'].strftime('%Y-%m-%d'),
                '箱体结束日期': pattern_info['box_end_date'].strftime('%Y-%m-%d'),
                '箱体最低价': pattern_info['box_low'],
                '箱体最高价': pattern_info['box_high'],
                '箱体中间价': pattern_info['box_mid'],
                '箱体价格区间百分比': pattern_info['box_range_ratio'],
                '大阳线日期': pattern_info['big_candle_date'].strftime('%Y-%m-%d'),
                '大阳线开盘价': pattern_info['big_candle_open'],
                '大阳线最高价': pattern_info['big_candle_high'],
                '大阳线最低价': pattern_info['big_candle_low'],
                '大阳线收盘价': pattern_info['big_candle_close'],
                '大阳线涨幅': pattern_info['big_candle_ratio']
            })
        
        # 创建DataFrame并保存
        df_save = pd.DataFrame(save_data)
        df_save.to_csv(save_file, index=False, encoding='utf-8-sig')
        print(f"筛选结果已保存到: {save_file}")
        
        return df_save
        
    def plot_all_matching_stocks(self, save_dir='./small_box_plots'):
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
            save_path = os.path.join(save_dir, f'{stock_code}_{safe_stock_name}_small_box.png')
            self.plot_kline_with_box(df, pattern_info, save_path)
        
        print(f"所有图形已保存到目录: {save_dir}")

if __name__ == "__main__":
    # 设置数据路径
    data_path = './daily_data_cache'
    
    # 创建分析器实例
    analyzer = SmallBoxBigCandleAnalyzer(
        data_path=data_path,
        lookback_days=30,               # 箱体期天数
        box_range_threshold=0.10,       # 箱体价格区间最大15%
        small_movement_threshold=0.02,  # 小波动K线的波动阈值（2%）
        small_movement_ratio=0.60,      # 小波动K线的比例要求（2%）
        big_candle_ratio=0.05           # 大阳线最小涨幅5%
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