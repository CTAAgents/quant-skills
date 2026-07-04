"""
从TDX获取所有ETF数据并保存
"""

import json
import os
import pandas as pd
from pathlib import Path

# TDX结果文件目录
TDX_DIR = r"C:\Users\yangd\.workbuddy\projects\c-Users-yangd-.workbuddy-workspace-files-20304-995cdc7c-716b-4b47-870e-6a353ac3fc59\995cdc7c-716b-4b47-870e-6a353ac3fc59\tool-results"

# ETF配置
ETF_CONFIG = [
    {"code": "510300", "setcode": "1", "name": "沪深300ETF", "category": "benchmark"},
    {"code": "512400", "setcode": "1", "name": "有色金属ETF", "category": "industry"},
    {"code": "510650", "setcode": "1", "name": "银行ETF", "category": "industry"},
    {"code": "516860", "setcode": "1", "name": "高端制造ETF", "category": "industry"},
    {"code": "159928", "setcode": "0", "name": "消费ETF", "category": "industry"},
    {"code": "512010", "setcode": "1", "name": "医药ETF", "category": "industry"},
    {"code": "515000", "setcode": "1", "name": "科技ETF", "category": "industry"},
    {"code": "511880", "setcode": "1", "name": "银华日利", "category": "defensive"},
]

# 缓存目录
CACHE_DIR = r"C:\Users\yangd\.workbuddy\skills\a-share-etf-momentum\cache"
os.makedirs(CACHE_DIR, exist_ok=True)


def find_tdx_file(code: str) -> str:
    """查找TDX结果文件"""
    for f in os.listdir(TDX_DIR):
        if f.startswith(f"mcp-connector-proxy-tdx-connector_tdx_kline-") and f.endswith(".txt"):
            file_path = os.path.join(TDX_DIR, f)
            try:
                with open(file_path, 'r', encoding='utf-8') as fh:
                    content = fh.read(500)
                    if f'"Code": "{code}"' in content:
                        return file_path
            except:
                pass
    return None


def parse_tdx_file(file_path: str) -> pd.DataFrame:
    """解析TDX K线数据文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    json_start = content.find('{')
    if json_start == -1:
        raise ValueError("无法找到JSON数据")

    json_str = content[json_start:]
    data = json.loads(json_str)

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


def main():
    """主函数"""
    print("=" * 60)
    print("ETF数据获取与解析")
    print("=" * 60)

    results = {}
    missing = []

    for etf in ETF_CONFIG:
        code = etf['code']
        name = etf['name']

        # 查找TDX文件
        tdx_file = find_tdx_file(code)
        if tdx_file is None:
            print(f"  {name} ({code}): 未找到TDX数据文件")
            missing.append(code)
            continue

        # 解析数据
        try:
            df = parse_tdx_file(tdx_file)
            results[code] = df

            # 保存到缓存
            cache_file = os.path.join(CACHE_DIR, f"{code}.csv")
            df.to_csv(cache_file, index=False)

            print(f"  {name} ({code}): {len(df)} 条记录, "
                  f"{df['date'].min().strftime('%Y-%m-%d')} 至 {df['date'].max().strftime('%Y-%m-%d')}, "
                  f"最新价: {df['close'].iloc[-1]:.3f}")
        except Exception as e:
            print(f"  {name} ({code}): 解析失败 - {e}")
            missing.append(code)

    print(f"\n成功获取: {len(results)} 只ETF")
    if missing:
        print(f"缺失: {missing}")

    # 计算动量
    print("\n" + "=" * 60)
    print("动量计算")
    print("=" * 60)

    # 绝对动量
    if "510300" in results:
        df = results["510300"]
        if len(df) >= 252:
            close_now = df['close'].iloc[-1]
            close_252ago = df['close'].iloc[-252]
            return_252d = (close_now / close_252ago) - 1
            is_bullish = return_252d > 0
            status = "多头市场 ✓" if is_bullish else "空头市场 ✗"
            print(f"\n【绝对动量】沪深300ETF 252日收益率: {return_252d:.2%} → {status}")

    # 相对动量
    print("\n【相对动量】行业ETF排名:")
    momentum_results = []
    for etf in ETF_CONFIG:
        if etf['category'] != 'industry':
            continue
        code = etf['code']
        if code in results and len(results[code]) >= 252:
            df = results[code]
            close_now = df['close'].iloc[-1]
            close_252ago = df['close'].iloc[-252]
            return_252d = (close_now / close_252ago) - 1
            momentum_results.append({
                'code': code,
                'name': etf['name'],
                'return_252d': return_252d
            })

    # 排序
    momentum_results.sort(key=lambda x: x['return_252d'], reverse=True)
    for i, r in enumerate(momentum_results, 1):
        print(f"  {i}. {r['name']} ({r['code']}): {r['return_252d']:.2%}")

    return results


if __name__ == "__main__":
    main()
