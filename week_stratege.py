import pandas as pd
import numpy as np
import datetime
import os
import requests
import time

# 导入股票价格下载工具
from utils import get_stock_info, get_daily

# ====================== 【你只需要填这里】 ======================
DOUBAO_API_KEY = "9c1f8d7a-ba9a-45da-9a8d-f893b1e1f6b9"
DOUBAO_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# 策略参数
WEEK_MA = 20
DAY_MA = 10
HOLD_DAYS = 10
STOP_LOSS = 0.05
STOP_PROFIT = 0.10
EXCEL_FILE = "股票策略_AI分析报告.xlsx"


# ---------------------- 2. 策略：周线上升 + 日线回调 ----------------------
def is_weekly_up(df_daily):
    print("DEBUG: 检查周线上升趋势...")
    week = df_daily.resample("W").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()
    print(f"DEBUG: 周线数据量: {len(week)}, 需要量: {WEEK_MA + 5}")
    if len(week) < WEEK_MA + 5:
        return False
    week["ma20"] = week["close"].rolling(WEEK_MA).mean()
    close_above_ma = week["close"].iloc[-1] > week["ma20"].iloc[-1]
    ma_rising = week["ma20"].iloc[-1] > week["ma20"].iloc[-2]
    print(f"DEBUG: 收盘价在MA20上方: {close_above_ma}, MA20上升: {ma_rising}")
    return close_above_ma and ma_rising

def check_buy(code):
    code_str = str(code)
    print(f"DEBUG: 检查股票 {code_str} 买入条件...")
    df = get_daily(code)
    if df is None:
        print(f"DEBUG: {code_str} 日线数据获取失败")
        return False, None
    if len(df) < 120:
        print(f"DEBUG: {code_str} 日线数据不足120条: {len(df)}")
        return False, None
    df["ma10"] = df["close"].rolling(DAY_MA).mean()
    callback3 = (df["close"].iloc[-3:] < df["ma10"].iloc[-3:]).all()
    trend_up = is_weekly_up(df)
    last = df.iloc[-1]
    close_above_open = last["close"] > last["open"]
    buy_ok = trend_up and callback3 and close_above_open
    print(f"DEBUG: {code_str} 回调条件: {callback3}, 趋势向上: {trend_up}, 收阳: {close_above_open}, 买入信号: {buy_ok}")
    return buy_ok, round(last["close"], 2) if buy_ok else (False, None)

# ---------------------- 3. 豆包联网AI 分析 ----------------------
def analyze_by_doubao(code, name):
    print(f"📡 正在联网分析 {code} {name}")

    prompt = f"""
你是A股专业投研分析师，必须**联网获取最新真实数据**，分析股票：{code} {name}。
严格按以下5点输出，不要多余内容，不要格式符号：

【1. 基本面】行业、主营业务、最新业绩、估值、核心竞争力
【2. 消息面】近7天重要公告、利好、利空、题材催化
【3. 技术面】周线上升+日线回调形态是否成立
【4. 综合评级】强烈关注 / 关注 / 观望 / 回避
【5. 买卖机会】适合买入原因、风险点、目标价、止损参考
"""

    try:
        # 尝试导入OpenAI库
        from openai import OpenAI
        import os
        
        # 从环境变量或配置中获取API KEY
        api_key = DOUBAO_API_KEY if DOUBAO_API_KEY else os.getenv('ARK_API_KEY')
        
        if not api_key:
            return "AI分析失败：未找到API_KEY"
        
        # 创建OpenAI客户端，指向火山方舟API
        client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=api_key,
        )
        
        # 调用responses.create API
        response = client.responses.create(
            model="doubao-seed-2-0-lite-260215",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        }
                    ],
                }
            ]
        )
        
        # 调试：打印完整响应
        print(f"DEBUG: API响应: {response}")
        
        # 提取响应内容
        try:
            if hasattr(response, 'output') and response.output:
                # 遍历output列表，寻找包含content的输出项（message类型）
                for output_item in response.output:
                    if hasattr(output_item, 'content') and output_item.content:
                        if len(output_item.content) > 0:
                            if hasattr(output_item.content[0], 'text') and output_item.content[0].text:
                                return output_item.content[0].text.strip()
                            return f"AI分析失败：output_item.content[0].text 为None"
                return f"AI分析失败：output中未找到有效的content"
        except Exception as e:
            print(f"DEBUG: 解析output响应失败: {str(e)}")
            
        try:
            if hasattr(response, 'choices') and response.choices:
                if len(response.choices) > 0:
                    if hasattr(response.choices[0], 'message') and response.choices[0].message:
                        if hasattr(response.choices[0].message, 'content') and response.choices[0].message.content:
                            return response.choices[0].message.content.strip()
                        return f"AI分析失败：choices[0].message.content 为None"
                    return f"AI分析失败：choices[0].message 为None"
                return f"AI分析失败：choices 为空列表"
        except Exception as e:
            print(f"DEBUG: 解析choices响应失败: {str(e)}")
            
        return f"AI分析失败：无法提取响应内容，响应类型：{type(response).__name__}"
            
    except ImportError:
        return "AI分析失败：未安装openai库，请执行 pip install openai"
    except Exception as e:
        return f"AI分析失败：{str(e)}"

# ---------------------- 4. 持仓Excel ----------------------
def load_position():
    if os.path.exists(EXCEL_FILE):
        return pd.read_excel(EXCEL_FILE)
    cols = ["代码","名称","买入价","止盈价","止损价","AI分析","更新时间"]
    return pd.DataFrame(columns=cols)

def save_position(df):
    df.to_excel(EXCEL_FILE, index=False)

# ---------------------- 5. 技术分析：纯选股逻辑 ----------------------
def technical_analysis():
    """纯技术分析选股，返回符合条件的股票列表"""
    print("=== 技术分析选股启动 ===")
    
    try:
        all_stocks = get_stock_info()
        if all_stocks is None:
            print("DEBUG: 未能获取股票列表，程序终止")
            return []
        pos = load_position()
        selected_stocks = []
        total = len(all_stocks)
        print(f"DEBUG: 总股票数: {total}, 持仓股票数: {len(pos)}")

        stocks_to_process = list(zip(all_stocks["code"], all_stocks["name"]))
        print(f"DEBUG: 开始处理 {len(stocks_to_process)} 只股票")
        
        for i, (code, name) in enumerate(stocks_to_process):
            print(f"\nDEBUG: 处理股票 {i+1}/{len(stocks_to_process)}: {code} {name}")
            if code in pos["代码"].values:
                print(f"DEBUG: {code} 已在持仓中，跳过")
                continue
            buy_ok, price = check_buy(code)
            if buy_ok and price:
                profit = round(price * (1 + STOP_PROFIT), 2)
                loss = round(price * (1 - STOP_LOSS), 2)
                selected_stocks.append((code, name, price, profit, loss))
                print(f"DEBUG: {code} 符合买入条件，买入价: {price}, 止盈价: {profit}, 止损价: {loss}")
            else:
                print(f"DEBUG: {code} 不符合买入条件")

        print(f"\nDEBUG: 技术分析完成，筛选出 {len(selected_stocks)} 只符合条件的股票")
        return selected_stocks
    except Exception as e:
        print(f"DEBUG: 技术分析执行错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

# ---------------------- 6. AI分析流程 ----------------------
def analyze_selected_stocks(selected_stocks):
    """对技术分析选出的股票进行AI分析"""
    if not selected_stocks:
        print("DEBUG: 没有需要AI分析的股票")
        return []
    
    print(f"\n=== AI分析启动，共分析 {len(selected_stocks)} 只股票 ===")
    
    analyzed_stocks = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    for code, name, price, profit, loss in selected_stocks:
        print(f"DEBUG: 开始AI分析 {code} {name}")
        ai_result = analyze_by_doubao(code, name)
        print(f"DEBUG: {code} AI分析结果: {ai_result[:100]}...")  # 打印结果前100个字符
        analyzed_stocks.append([code, name, price, profit, loss, ai_result, now])
        print(f"DEBUG: {code} AI分析完成，结果已添加到记录")
    
    print(f"\nDEBUG: AI分析完成，共分析 {len(analyzed_stocks)} 只股票")
    return analyzed_stocks

# ---------------------- 7. 主流程：灵活调用 ----------------------
def scan_and_analyze(use_ai=True):
    """全市场扫描选股主流程
    
    Args:
        use_ai: 是否对选出的股票进行AI分析，默认为True
    """
    print("=== 全市场扫描选股启动 ===")
    
    try:
        # 技术分析选股
        selected_stocks = technical_analysis()
        
        if not selected_stocks:
            print("\n⚠️  未找到符合条件的股票")
            return
        
        # 加载持仓
        pos = load_position()
        
        if use_ai:
            # AI分析
            analyzed_stocks = analyze_selected_stocks(selected_stocks)
            
            # 保存包含AI分析的结果
            if analyzed_stocks:
                new_df = pd.DataFrame(analyzed_stocks, columns=pos.columns)
                final = pd.concat([pos, new_df], ignore_index=True)
                save_position(final)
                print("\n✅ 今日完成选股 + AI 分析：")
                print(new_df[["代码","名称","买入价","止盈价","止损价"]].to_string(index=False))
                print(f"\n📄 完整报告已保存到：{EXCEL_FILE}")
        else:
            # 仅保存技术分析结果（AI分析字段留空）
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            tech_only_stocks = [list(stock) + ["", now] for stock in selected_stocks]
            
            if tech_only_stocks:
                new_df = pd.DataFrame(tech_only_stocks, columns=pos.columns)
                final = pd.concat([pos, new_df], ignore_index=True)
                save_position(final)
                print("\n✅ 今日完成选股（仅技术分析）：")
                print(new_df[["代码","名称","买入价","止盈价","止损价"]].to_string(index=False))
                print(f"\n📄 完整报告已保存到：{EXCEL_FILE}")
                
    except Exception as e:
        print(f"DEBUG: 程序执行错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    scan_and_analyze(use_ai=False)