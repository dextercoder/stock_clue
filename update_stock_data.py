#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增量更新股票数据脚本
用于更新daily_data_cache中的股票数据，只获取最新的股价
"""

import sys
import os
from utils import get_daily_incremental, get_stock_info


def update_all_stocks():
    """更新所有股票的最新数据"""
    print("开始更新所有股票的最新数据...")
    
    # 获取股票列表
    stock_df = get_stock_info()
    print(f"共 {len(stock_df)} 只股票需要更新")
    
    # 逐个更新
    success_count = 0
    fail_count = 0
    
    for index, row in stock_df.iterrows():
        code = row['code']
        name = row['name']
        print(f"\n=== 更新股票: {code} {name} ===")
        
        try:
            df = get_daily_incremental(code)
            if df is not None:
                success_count += 1
                print(f"✓ 更新成功: {code} {name}")
            else:
                fail_count += 1
                print(f"✗ 更新失败: {code} {name}")
        except Exception as e:
            fail_count += 1
            print(f"✗ 更新出错: {code} {name} - {str(e)}")
    
    print(f"\n=== 更新完成 ===")
    print(f"成功: {success_count} 只股票")
    print(f"失败: {fail_count} 只股票")


def update_specific_stocks(codes):
    """更新指定股票的最新数据"""
    print(f"开始更新指定的 {len(codes)} 只股票...")
    
    success_count = 0
    fail_count = 0
    
    for code in codes:
        print(f"\n=== 更新股票: {code} ===")
        
        try:
            df = get_daily_incremental(code)
            if df is not None:
                success_count += 1
                print(f"✓ 更新成功: {code}")
            else:
                fail_count += 1
                print(f"✗ 更新失败: {code}")
        except Exception as e:
            fail_count += 1
            print(f"✗ 更新出错: {code} - {str(e)}")
    
    print(f"\n=== 更新完成 ===")
    print(f"成功: {success_count} 只股票")
    print(f"失败: {fail_count} 只股票")


if __name__ == "__main__":
    print("股票数据增量更新脚本")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        # 如果提供了股票代码参数，只更新指定的股票
        stock_codes = sys.argv[1:]
        update_specific_stocks(stock_codes)
    else:
        # 否则更新所有股票
        update_all_stocks()
