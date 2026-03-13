import tushare as ts
import pandas as pd
import numpy as np
import datetime
import os
import requests
import time

# 初始化tushare（直接传入token避免文件写入权限问题）
pro = ts.pro_api('c0df5cc9da343b356dc1e58a4b649053a4b3bbe440bd13129f0d7935')

# API限流参数
API_RATE_LIMITS = {
    'stock_basic': {'delay': 1, 'max_per_hour': 1},  # 每小时1次
    'daily': {'delay': 2, 'max_per_minute': 200}     # 每分钟200次
}

# 请求计数
request_counts = {
    'stock_basic': {'last_request': 0, 'count': 0},
    'daily': {'last_request': 0, 'count': 0}
}

def retry_api(max_retries=3, backoff_factor=2, retry_on=[429, 500, 502, 503, 504]):
    """API调用重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e)
                    print(f"DEBUG: API调用失败 (尝试 {retries+1}/{max_retries+1}): {error_msg}")
                    
                    # 检查是否是需要重试的错误
                    if any(code in error_msg for code in [str(code) for code in retry_on]):
                        # 检查是否是接口限制错误
                        if "每小时最多访问该接口" in error_msg or "429" in error_msg:
                            print("DEBUG: API限流错误，等待更长时间...")
                            wait_time = backoff_factor ** retries * 60  # 分钟级等待
                        else:
                            wait_time = backoff_factor ** retries
                        
                        print(f"DEBUG: {wait_time}秒后重试...")
                        time.sleep(wait_time)
                        retries += 1
                    else:
                        # 其他错误不重试
                        raise e
            
            # 超过最大重试次数
            print(f"DEBUG: API调用失败，已超过最大重试次数 {max_retries}")
            return None
        return wrapper
    return decorator

def api_rate_limit(api_name):
    """API请求限流控制"""
    if api_name not in API_RATE_LIMITS:
        time.sleep(3)  # 默认延迟3秒
        return
    
    limit_info = API_RATE_LIMITS[api_name]
    count_info = request_counts[api_name]
    current_time = time.time()
    
    # 重置计数（每分钟或每小时）
    if api_name == 'stock_basic':
        # 每小时重置一次计数
        if current_time - count_info['last_request'] > 3600:
            count_info['count'] = 0
    elif api_name == 'daily':
        # 每分钟重置一次计数
        if current_time - count_info['last_request'] > 60:
            count_info['count'] = 0
    
    # 检查是否超过限制
    if api_name == 'stock_basic' and count_info['count'] >= limit_info['max_per_hour']:
        # 等待到下一个小时
        wait_time = 3600 - (current_time - count_info['last_request']) % 3600 + 1
        print(f"DEBUG: 超过stock_basic接口限制，等待 {wait_time:.0f} 秒")
        time.sleep(wait_time)
        count_info['count'] = 0
    elif api_name == 'daily' and count_info['count'] >= limit_info['max_per_minute']:
        # 等待到下一分钟
        wait_time = 60 - (current_time - count_info['last_request']) % 60 + 1
        print(f"DEBUG: 超过daily接口限制，等待 {wait_time:.0f} 秒")
        time.sleep(wait_time)
        count_info['count'] = 0
    
    # 基本延迟
    time.sleep(limit_info['delay'])
    
    # 更新计数
    count_info['count'] += 1
    count_info['last_request'] = current_time

@retry_api(max_retries=3, backoff_factor=2)
def call_stock_basic():
    """调用stock_basic API"""
    return pro.stock_basic(
        exchange='', 
        list_status='L', 
        fields='ts_code,symbol,name'
    )

@retry_api(max_retries=3, backoff_factor=2)
def call_daily(ts_code, start_date, end_date):
    """调用daily API"""
    return pro.daily(
        ts_code=ts_code, 
        start_date=start_date, 
        end_date=end_date
    )

# ---------------------- 1. 获取股票列表 & 数据 ----------------------
def get_stock_info():
    print("DEBUG: 开始获取股票列表...")
    cache_file = "stock_list_cache.csv"
    cache_expiry = 24 * 3600  # 24小时有效期
    
    # 检查缓存是否存在且未过期
    try:
        if os.path.exists(cache_file):
            cache_time = os.path.getmtime(cache_file)
            current_time = time.time()
            if current_time - cache_time < cache_expiry:
                print("DEBUG: 使用缓存的股票列表")
                # 明确指定股票代码为字符串类型，避免pandas自动转换为整数
                df = pd.read_csv(cache_file, dtype={'code': str})
                print(f"DEBUG: 从缓存获取到 {len(df)} 只股票")
                return df
    except Exception as e:
        print(f"DEBUG: 读取股票列表缓存失败: {str(e)}")
    
    # 缓存不存在或已过期，调用API
    try:
        print("DEBUG: 调用tushare API获取股票列表...")
        api_rate_limit('stock_basic')  # 限流控制
        df = call_stock_basic()
        
        print(f"DEBUG: 获取到 {len(df)} 只股票")
        
        # 重命名列名以保持兼容
        df = df[['symbol', 'name']]
        df.columns = ['code', 'name']
        
        # 筛选条件：排除ST、退市股票，只保留6、0、3开头的6位数字股票代码
        df = df[~df["name"].str.contains("ST|退", na=False)]
        df = df[df["code"].str.startswith(("6", "0", "3"))]
        # 确保股票代码是6位数字
        df = df[df["code"].str.len() == 6]
        
        print(f"DEBUG: 筛选后剩余 {len(df)} 只股票")
        
        # 保存到缓存
        try:
            df.to_csv(cache_file, index=False, encoding='utf-8-sig')
            print("DEBUG: 股票列表已缓存为CSV格式")
        except Exception as e:
            print(f"DEBUG: 保存股票列表缓存失败: {str(e)}")
        
        return df
    except Exception as e:
        print(f"DEBUG: 获取股票列表失败: {str(e)}")
        
        # 尝试使用本地保存的股票列表文件作为最后手段
        local_stock_file = "local_stock_list.csv"
        if os.path.exists(local_stock_file):
            try:
                print("DEBUG: 尝试使用本地保存的股票列表文件")
                # 明确指定股票代码为字符串类型
                df = pd.read_csv(local_stock_file, dtype={'code': str})
                # 对本地文件也应用相同的筛选条件
                df = df[~df["name"].str.contains("ST|退", na=False)]
                df = df[df["code"].str.startswith(("6", "0", "3"))]
                df = df[df["code"].str.len() == 6]
                print(f"DEBUG: 从本地文件筛选后获取到 {len(df)} 只股票")
                return df
            except Exception as e:
                print(f"DEBUG: 读取本地股票列表文件失败: {str(e)}")
        
        # 如果本地文件也不存在，使用一个小型的测试股票列表
        print("DEBUG: 使用最小测试股票列表")
        test_stocks = [
            ["000001", "平安银行"],
            ["000002", "万科A"],
            ["600000", "浦发银行"]
        ]
        df = pd.DataFrame(test_stocks, columns=["code", "name"])
        
        # 保存到本地文件，供下次使用
        try:
            df.to_csv(local_stock_file, index=False, encoding='utf-8-sig')
            print("DEBUG: 测试股票列表已保存到本地文件(CSV格式)")
        except Exception as e:
            print(f"DEBUG: 保存本地股票列表失败: {str(e)}")
            
        print(f"DEBUG: 使用测试股票列表，共 {len(df)} 只股票")
        return df

def get_daily(code):
    code_str = str(code)
    print(f"DEBUG: 获取股票 {code_str} 日线数据...")
    
    # 创建缓存目录
    cache_dir = "daily_data_cache"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    
    # 缓存文件路径
    code_str = str(code)
    cache_file = os.path.join(cache_dir, f"{code_str}_daily.csv")
    cache_expiry = 24 * 3600  # 1天有效期
    
    # 检查缓存是否存在且未过期
    try:
        if os.path.exists(cache_file):
            cache_time = os.path.getmtime(cache_file)
            current_time = time.time()
            if current_time - cache_time < cache_expiry:
                print(f"DEBUG: 使用缓存的 {code_str} 日线数据")
                df = pd.read_csv(cache_file, parse_dates=['date'], index_col='date')
                print(f"DEBUG: 从缓存获取到 {len(df)} 条日线数据")
                print(f"DEBUG: 数据日期范围: {df.index.min()} 到 {df.index.max()}")
                return df
    except Exception as e:
        print(f"DEBUG: 读取 {code_str} 日线数据缓存失败: {str(e)}")
    
    # 缓存不存在或已过期，调用API
    try:
        # API限流控制
        api_rate_limit('daily')
        
        # 转换为tushare支持的ts_code格式
        code_str = str(code)
        if code_str.startswith("6"):
            ts_code = f"{code_str}.SH"  # 上海证券交易所
        else:
            ts_code = f"{code_str}.SZ"  # 深圳证券交易所
        
        print(f"DEBUG: 转换为tushare代码: {ts_code}")
        
        # 设置日期范围（最近3年）
        end_date = datetime.datetime.now().strftime("%Y%m%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=3*365)).strftime("%Y%m%d")
        
        # 使用tushare获取日线数据
        df = call_daily(ts_code, start_date, end_date)
        
        if df.empty:
            print(f"DEBUG: 未获取到 {code_str} 的数据")
            return None
        
        # 重命名和筛选列
        df = df[['trade_date', 'open', 'high', 'low', 'close', 'vol']]
        df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        
        # 转换日期格式并设置索引
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 按日期升序排序
        df.sort_index(inplace=True)
        
        print(f"DEBUG: 获取到 {len(df)} 条日线数据")
        print(f"DEBUG: 数据日期范围: {df.index.min()} 到 {df.index.max()}")
        
        # 保存到缓存
        try:
            df.to_csv(cache_file, encoding='utf-8-sig')
            print(f"DEBUG: {code_str} 日线数据已缓存为CSV格式")
        except Exception as e:
            print(f"DEBUG: 保存 {code_str} 日线数据缓存失败: {str(e)}")
        
        return df
    except Exception as e:
        print(f"DEBUG: 获取 {code_str} 日线数据失败: {str(e)}")
        return None
