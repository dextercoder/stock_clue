import pandas as pd
import os
import utils

# 从CSV文件读取数据并测试AI分析功能
def get_ai_from_csv():
    print("从CSV文件读取数据并测试AI分析功能...")
    
    # 读取CSV文件
    csv_file = './small_box_stocks.csv'
    if not os.path.exists(csv_file):
        print(f"错误：文件 {csv_file} 不存在")
        return
    
    df = pd.read_csv(csv_file)
    print(f"成功读取CSV文件，共包含 {len(df)} 条记录")
    
    # 提取所有股票数据
    if len(df) == 0:
        print("错误：CSV文件为空")
        return
    
    print(f"准备分析 {len(df)} 只股票")
    
    # 准备测试数据
    selected_stocks = []
    for index, row in df.iterrows():
        stock_code = row['股票代码']
        stock_name = row['股票名称']
        price = row['大阳线收盘价']
        # 简单设置获利点和止损点
        profit = price * 1.1  # 10% 获利
        loss = row['箱体最低价']  # 箱体底部作为止损
        selected_stocks.append((stock_code, stock_name, price, profit, loss))
    
    # 调用AI分析
    analyzed_stocks = utils.analyze_selected_stocks(selected_stocks)
    
    if not analyzed_stocks:
        print("AI分析失败，没有生成分析结果")
        return
    
    # 打印分析结果
    for code, name, price, profit, loss, ai_result, analyze_time in analyzed_stocks:
        print(f"\n股票：{code} {name}")
        print(f"价格：{price}")
        print(f"建议获利点：{profit}")
        print(f"建议止损点：{loss}")
        print(f"分析时间：{analyze_time}")
        print(f"\nAI分析结果：")
        print(ai_result)
    
    # 准备保存数据
    save_data = []
    for code, name, price, profit, loss, ai_result, analyze_time in analyzed_stocks:
        save_data.append({
            '股票代码': code,
            '股票名称': name,
            '价格': price,
            '建议获利点': profit,
            '建议止损点': loss,
            'AI分析结果': ai_result,
            '分析时间': analyze_time
        })
    
    # 创建DataFrame并保存到Excel
    df_save = pd.DataFrame(save_data)
    save_file = './small_box_stocks_with_analysis.xlsx'
    df_save.to_excel(save_file, index=False)
    print(f"\nAI分析结果已保存到: {save_file}")
    
    return df_save

if __name__ == "__main__":
    get_ai_from_csv()
