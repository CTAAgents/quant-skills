"""
使用TDX获取ETF数据并运行回测
"""

import json
import pandas as pd
from datetime import datetime

# TDX数据文件路径
TDX_FILE = r"C:\Users\yangd\.workbuddy\projects\c-Users-yangd-.workbuddy-workspace-files-20304-995cdc7c-716b-4b47-870e-6a353ac3fc59\995cdc7c-716b-4b47-870e-6a353ac3fc59\tool-results\mcp-connector-proxy-tdx-connector_tdx_kline-1782450195268-c15e05.txt"

def parse_tdx_data(file_path: str) -> pd.DataFrame:
    """解析TDX K线数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 找到JSON开始位置
    json_start = content.find('{')
    if json_start == -1:
        raise ValueError("无法找到JSON数据")

    json_str = content[json_start:]
    data = json.loads(json_str)

    # 解析K线数据
    records = []
    for item in data['ListItem']:
        values = item['Item']
        records.append({
            'date': pd.to_datetime(values[0], format='%Y%m%d'),
            'open': float(values[2]),
            'high': float(values[3]),
            'low': float(values[4]),
            'close': float(values[5]),
            'amount': float(values[6]),
            'volume': float(values[8])
        })

    df = pd.DataFrame(records)
    df = df.sort_values('date').reset_index(drop=True)
    return df


if __name__ == "__main__":
    # 解析510300数据
    df = parse_tdx_data(TDX_FILE)

    print(f"数据解析完成:")
    print(f"  记录数: {len(df)}")
    print(f"  时间范围: {df['date'].min().strftime('%Y-%m-%d')} 至 {df['date'].max().strftime('%Y-%m-%d')}")
    print(f"  最新收盘价: {df['close'].iloc[-1]:.3f}")

    # 计算252日收益率
    if len(df) >= 252:
        close_now = df['close'].iloc[-1]
        close_252ago = df['close'].iloc[-252]
        return_252d = (close_now / close_252ago) - 1
        print(f"  252日收益率: {return_252d:.2%}")

    # 保存为CSV
    output_file = r"C:\Users\yangd\.workbuddy\skills\a-share-etf-momentum\cache\510300_tdx.csv"
    df.to_csv(output_file, index=False)
    print(f"\n数据已保存到: {output_file}")
