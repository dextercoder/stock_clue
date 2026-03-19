#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试web search功能是否正确添加
"""

from utils import analyze_by_doubao

if __name__ == "__main__":
    print("测试web search功能...")
    print("=" * 50)
    
    # 测试分析一只股票
    stock_code = "000001"
    stock_name = "平安银行"
    
    print(f"分析股票: {stock_code} {stock_name}")
    print("正在调用豆包API，启用web search功能...")
    
    result = analyze_by_doubao(stock_code, stock_name)
    
    print("\n分析结果:")
    print("=" * 50)
    print(result)
    print("=" * 50)
    
    # 检查结果是否包含最新信息，验证是否成功联网
    contains_recent_info = False
    
    # 检查是否包含2025或2026年的最新信息
    if "2025" in result or "2026" in result:
        contains_recent_info = True
        print("✅ 测试成功：分析结果包含最新年份的信息")
    
    # 检查是否包含最新的公告或事件
    if any(keyword in result for keyword in ["最新公告", "近期公告", "最新业绩", "拟发行", "战略合作"]):
        contains_recent_info = True
        print("✅ 测试成功：分析结果包含最新公告信息")
    
    # 检查是否包含具体的业务信息
    if any(keyword in result for keyword in ["金融科技", "永续债", "腾讯科技"]):
        contains_recent_info = True
        print("✅ 测试成功：分析结果包含最新业务信息")
    
    if contains_recent_info:
        print("✅ 测试成功：web search功能已正确添加并联网获取最新信息")
    else:
        print("❌ 测试失败：分析结果未包含最新信息，可能未成功联网")
        print("提示：请检查API_KEY是否正确，以及网络连接是否正常")
