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

class StockAnalyzer:
    def __init__(self, data_path, lookback_days=40, min_down_days=3, big_candle_ratio=0.05):
        self.data_path = data_path
        self.lookback_days = lookback_days
        self.min_down_days = min_down_days
        self.big_candle_ratio = big_candle_ratio
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
    
    def get_weekly_data(self, daily_df):
        """将日线数据转换为周线数据"""
        if len(daily_df) < 20:  # 至少需要20个交易日的数据
            return None
        
        # 设置日期为索引
        df = daily_df.set_index('date')
        
        # 按周重采样并计算OHLC数据
        weekly_df = df.resample('W').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()  # 删除空值行
        
        # 重置索引，保留date列
        weekly_df = weekly_df.reset_index()
        
        return weekly_df
    
    def is_in_weekly_uptrend_channel(self, weekly_df, sma_period=10, channel_multiplier=2):
        """判断周线是否处于上升通道
        
        参数:
            weekly_df: 周线数据
            sma_period: 移动平均线周期
            channel_multiplier: 通道宽度的标准差倍数
            
        返回:
            bool: 是否处于上升通道
        """
        if len(weekly_df) < sma_period * 2:  # 至少需要两倍周期的数据
            return False
        
        # 计算移动平均线
        weekly_df['sma'] = weekly_df['close'].rolling(window=sma_period).mean()
        
        # 计算标准差
        weekly_df['std'] = weekly_df['close'].rolling(window=sma_period).std()
        
        # 计算通道上轨和下轨
        weekly_df['upper_channel'] = weekly_df['sma'] + (weekly_df['std'] * channel_multiplier)
        weekly_df['lower_channel'] = weekly_df['sma'] - (weekly_df['std'] * channel_multiplier)
        
        # 获取最近的一段数据用于判断
        recent_data = weekly_df.tail(sma_period)
        
        # 检查1: 移动平均线是否呈上升趋势
        sma_slope = np.polyfit(range(len(recent_data['sma'])), recent_data['sma'], 1)[0]
        if sma_slope <= 0:  # 斜率非正，不是上升趋势
            return False
        
        # 检查2: 大部分价格是否在通道内
        in_channel_count = ((recent_data['close'] >= recent_data['lower_channel']) & 
                           (recent_data['close'] <= recent_data['upper_channel'])).sum()
        if in_channel_count < len(recent_data) * 0.7:  # 至少70%的时间在通道内
            return False
        
        # 检查3: 最近的收盘价是否在通道内且接近或高于移动平均线
        latest = recent_data.iloc[-1]
        if latest['close'] < latest['lower_channel'] or latest['close'] > latest['upper_channel']:
            return False
        
        return True
    
    def find_continuous_fall_with_big_candle(self, df, stock_code=None, price_proximity_threshold=0.02):
        """查找连续下跌后出现大阳线的模式
        
        参数:
            df: 股票日线数据
            stock_code: 股票代码（可选，如果传入则优先使用）
            price_proximity_threshold: 当前价格与大阳线中间价格的接近阈值（百分比）
            
        返回:
            匹配的模式信息或None
        """
        if len(df) < self.lookback_days:
            return None
        
        # 获取最近一段时间的数据
        recent_data = df.tail(self.lookback_days).copy()
        
        # 计算每日涨跌幅
        recent_data['change_ratio'] = (recent_data['close'] - recent_data['open']) / recent_data['open']
        recent_data['is_down'] = recent_data['close'] < recent_data['open']
        
        # 查找连续下跌的区间
        for i in range(len(recent_data) - self.min_down_days):
            # 检查是否有连续下跌的天数
            down_period = recent_data.iloc[i:i+self.min_down_days]
            if down_period['is_down'].all():
                # 检查下一天是否是大阳线
                next_day = recent_data.iloc[i+self.min_down_days]
                if next_day['change_ratio'] >= self.big_candle_ratio:
                    # 找到匹配的模式
                    current_candle = next_day
                    candle_middle = (current_candle['high'] + current_candle['low']) / 2
                    current_price = recent_data['close'].iloc[-1]
                    
                    # 检查当前价格是否在大阳线中间价格附近
                    price_diff = abs(current_price - candle_middle) / candle_middle
                    if price_diff > price_proximity_threshold:
                        continue  # 当前价格与大阳线中间价格差距太大，跳过
                    
                    # 获取股票代码和名称
                    if stock_code is None:
                        stock_code = recent_data['code'].iloc[0] if 'code' in recent_data.columns else 'unknown'
                    # 确保股票代码是纯数字（去除可能的后缀）
                    stock_code = stock_code.split('_')[0].strip()
                    stock_name = self.stock_name_map.get(stock_code, stock_code)
                    
                    pattern_info = {
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'big_candle_date': current_candle['date'],
                        'big_candle_open': current_candle['open'],
                        'big_candle_high': current_candle['high'],
                        'big_candle_low': current_candle['low'],
                        'big_candle_close': current_candle['close'],
                        'candle_middle': candle_middle,
                        'current_price': current_price,
                        'price_diff_ratio': price_diff,  # 新增：当前价格与大阳线中间价格的差异百分比
                        'continuous_fall_days': self.min_down_days,
                        'candle_ratio': current_candle['change_ratio']
                    }
                    return pattern_info
        
        return None
    
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
                
                # 计算周线数据
                weekly_df = self.get_weekly_data(df)
                if weekly_df is None:
                    continue  # 周线数据不足，跳过
                
                # 检查是否处于周线上升通道
                if not self.is_in_weekly_uptrend_channel(weekly_df):
                    continue  # 不在周线上升通道，跳过
                
                # 查找符合条件的模式（传递df和stock_code）
                pattern_info = self.find_continuous_fall_with_big_candle(df, stock_code=stock_code)
                if pattern_info:
                    print(f"找到匹配模式的股票: {pattern_info['stock_name']} ({pattern_info['stock_code']})")
                    print(f"  大阳线日期: {pattern_info['big_candle_date'].strftime('%Y-%m-%d')}")
                    print(f"  大阳线涨幅: {pattern_info['candle_ratio']:.2%}")
                    print(f"  当前价格: {pattern_info['current_price']:.2f}")
                    print(f"  大阳线中间价格: {pattern_info['candle_middle']:.2f}")
                    print(f"  价格差异: {pattern_info['price_diff_ratio']:.2%}")
                    print()
                    self.matching_stocks.append((df, pattern_info))
            
            except Exception as e:
                print(f"分析股票 {stock_file} 时出错: {str(e)}")
        
        print(f"分析完成，共找到 {len(self.matching_stocks)} 只符合条件的股票")
    
    def plot_kline_with_box(self, df, pattern_info, save_path):
        """绘制K线图并标记方框"""
        # 获取最近60天的数据用于绘图
        plot_data = df.tail(60).copy()
        
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
        
        # 标记大阳线位置
        big_candle_idx = plot_data[plot_data['date'] == pattern_info['big_candle_date']].index[0]
        big_candle_row = plot_data.loc[big_candle_idx]
        
        # 绘制方框：从大阳线的最低价到最高价，左右各扩展2天
        box_left = big_candle_row['date_num'] - 2
        box_right = big_candle_row['date_num'] + 2
        box_bottom = big_candle_row['low']
        box_top = big_candle_row['high']
        
        # 绘制方框
        rect = plt.Rectangle((box_left, box_bottom), box_right - box_left, box_top - box_bottom,
                           facecolor='blue', alpha=0.2, edgecolor='blue', linewidth=2)
        ax.add_patch(rect)
        
        # 添加文本标签
        ax.text(box_right + 0.5, (box_top + box_bottom) / 2, 
               f'大阳线\n涨幅: {pattern_info["candle_ratio"]:.2%}', 
               va='center', fontsize=10, color='blue')
        
        # 绘制中间价格线
        ax.axhline(y=pattern_info['candle_middle'], color='purple', linestyle='--', alpha=0.7,
                  label=f'大阳线中间价: {pattern_info["candle_middle"]:.2f}')
        
        # 设置标题和标签
        stock_code = pattern_info['stock_code']
        stock_name = pattern_info.get('stock_name', stock_code)
        
        # 在图表左上角添加股票名称和代码（更明显的位置）
        ax.text(0.02, 0.95, f'{stock_name} ({stock_code})', 
                transform=ax.transAxes, 
                fontsize=14, fontweight='bold', 
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
        
        # 设置主标题
        ax.set_title(f'连续下跌后大阳线模式 - K线图\n大阳线日期: {pattern_info["big_candle_date"].strftime("%Y-%m-%d")}', fontsize=12)
        ax.set_xlabel('日期')
        ax.set_ylabel('价格')
        ax.grid(True, alpha=0.3)
        
        # 添加股票名称到图例
        ax.legend(title=f'{stock_name} ({stock_code})')
        
        # 保存或显示图像
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图形已保存到: {save_path}")
        else:
            plt.show()
        
        plt.close()
    
    def save_matching_stocks(self, save_file='./matching_stocks.csv'):
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
                '大阳线日期': pattern_info['big_candle_date'].strftime('%Y-%m-%d'),
                '大阳线涨幅': pattern_info['candle_ratio'],
                '大阳线开盘价': pattern_info['big_candle_open'],
                '大阳线最高价': pattern_info['big_candle_high'],
                '大阳线最低价': pattern_info['big_candle_low'],
                '大阳线收盘价': pattern_info['big_candle_close'],
                '大阳线中间价': pattern_info['candle_middle'],
                '当前价格': pattern_info['current_price'],
                '价格差异百分比': pattern_info['price_diff_ratio'],
                '连续下跌天数': pattern_info['continuous_fall_days']
            })
        
        # 创建DataFrame并保存
        df_save = pd.DataFrame(save_data)
        df_save.to_csv(save_file, index=False, encoding='utf-8-sig')
        print(f"筛选结果已保存到: {save_file}")
        print(f"共保存 {len(df_save)} 只股票")
        
        return df_save
        
    def plot_all_matching_stocks(self, save_dir='./pattern_plots'):
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
            save_path = os.path.join(save_dir, f'{stock_code}_{safe_stock_name}_pattern.png')
            self.plot_kline_with_box(df, pattern_info, save_path)
        
        print(f"所有图形已保存到目录: {save_dir}")

if __name__ == "__main__":
    # 设置数据路径
    data_path = './daily_data_cache'
    
    # 创建分析器实例
    analyzer = StockAnalyzer(
        data_path=data_path,
        lookback_days=40,
        min_down_days=3,
        big_candle_ratio=0.05
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