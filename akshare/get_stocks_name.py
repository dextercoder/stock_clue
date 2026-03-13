import akshare as ak
import pandas as pd

def get_all_a_stock_codes():
    """
    获取A股所有股票代码及基础信息
    返回：DataFrame格式，包含代码、名称、板块、交易所等信息
    """
    try:
        # 1. 获取全市场A股列表（包含沪市、深市、北交所）
        # stock_info_a_code_name 接口返回最新A股代码-名称对照表
        stock_df = ak.stock_info_a_code_name()
        
        # 2. 补充股票所属板块/交易所信息（通过代码开头判断）
        def get_stock_board(code):
            """根据代码开头判断股票所属板块"""
            code_prefix = code[:3]  # 取代码前3位（科创板/创业板需前3位）
            code_first = code[0]    # 取代码第1位（快速分类）
            
            if code_first == '6':
                if code_prefix == '688':
                    return '沪市-科创板'
                else:
                    return '沪市-主板'
            elif code_first == '0':
                return '深市-主板/中小板'
            elif code_first == '3':
                return '深市-创业板'
            elif code_first in ['4', '8', '9']:
                return '北交所'
            else:
                return '未知板块'
        
        # 3. 新增板块列
        stock_df['板块'] = stock_df['code'].apply(get_stock_board)
        
        # 4. 重命名列（方便理解）
        stock_df.rename(columns={'code': '股票代码', 'name': '股票名称'}, inplace=True)
        
        # 5. 按板块排序
        stock_df.sort_values('板块', inplace=True)
        
        return stock_df
    except:
        pass

if __name__ == '__main__':
    # 获取所有A股代码
    all_stocks = get_all_a_stock_codes()
    
    # 打印前10行预览
    print("A股股票列表（前10条）：")
    print(all_stocks.head(10))
    
    # 保存为Excel文件（方便查看和使用）
    all_stocks.to_excel('A股所有股票代码列表.xlsx', index=False)
    print("\n数据已保存到：A股所有股票代码列表.xlsx")
    
    # 统计各板块数量
    board_count = all_stocks['板块'].value_counts()
    print("\n各板块股票数量：")
    print(board_count)