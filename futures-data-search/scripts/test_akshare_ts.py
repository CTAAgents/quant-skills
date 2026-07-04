#!/usr/bin/env python3
"""Test AKShare realtime data for term structure calculation"""
import akshare as ak

df = ak.futures_zh_realtime()
print(f'Total rows: {len(df)}')

varieties = ['cs', 'sp', 'rb', 'hc', 'FG', 'a', 'PK', 'SA', 'i', 'si']
varieties_upper = [v.upper() for v in varieties]

for v in varieties_upper:
    subset = df[df['symbol'].str.startswith(v, na=False)]
    if len(subset) > 0:
        print(f'\n{v}:')
        subset_sorted = subset.sort_values('symbol')
        for _, row in subset_sorted.iterrows():
            trade = row.get('trade', '')
            volume = row.get('volume', '')
            position = row.get('position', '')
            print(f"  {row['symbol']:12s} trade={str(trade):>8s} volume={str(volume):>8s} position={str(position):>8s}")
    else:
        print(f'\n{v}: (no data)')
