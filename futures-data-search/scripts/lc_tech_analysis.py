#!/usr/bin/env python3
"""
碳酸锂(LC) Phase 1 技术指标分析
L1-L4四层打分系统
分析日期: 2026-06-28
"""

import duckdb
import pandas as pd
import numpy as np
import json

# ============ 1. 数据获取 ============
DB_PATH = 'collectors/exchange_data/data/futures_data.duckdb'

con = duckdb.connect(DB_PATH, read_only=True)

# 获取LC日线数据 (index_continuous, lc品种汇总数据)
lc = con.execute("""
    SELECT trade_date, open, high, low, close, volume, open_interest
    FROM daily_data
    WHERE symbol = 'lc' AND exchange = 'GFEX'
    ORDER BY trade_date ASC
""").fetchdf()

# 获取LC所有合约期限结构（最新交易日）
lc_contracts = con.execute("""
    SELECT trade_date, symbol, open, high, low, close, volume, open_interest
    FROM daily_data
    WHERE exchange = 'GFEX' AND variety = 'lc'
      AND trade_date = (SELECT MAX(trade_date) FROM daily_data WHERE symbol = 'lc' AND exchange = 'GFEX')
    ORDER BY symbol
""").fetchdf()

con.close()

data = lc.sort_values('trade_date').reset_index(drop=True)
opens = data['open'].values.astype(float)
highs = data['high'].values.astype(float)
lows = data['low'].values.astype(float)
closes = data['close'].values.astype(float)
volumes = data['volume'].values.astype(float)
ois = data['open_interest'].values.astype(float)
dates = data['trade_date'].values

n = len(data)
latest_idx = n - 1

# ============ 2. L1: 萌芽信号 (55分) ============
l1_score = 0
l1_details = {}

# 1) OI三角
oi_chg_pct = (ois[-1] - ois[0]) / ois[0] * 100 if n > 1 else 0
oi_chg_1d = (ois[-1] - ois[-2]) / ois[-2] * 100 if n > 1 else 0
if oi_chg_1d > 2:
    l1_details['OI三角'] = '5分: OI日增{:.1f}%, 资金流入'.format(oi_chg_1d)
    l1_score += 5
elif oi_chg_1d < -2:
    l1_details['OI三角'] = '3分: OI日减{:.1f}%, 资金流出'.format(abs(oi_chg_1d))
    l1_score += 3
else:
    l1_details['OI三角'] = '2分: OI变化{:.1f}%, 温和'.format(oi_chg_1d)
    l1_score += 2

# 2) 基差 (主力合约 vs 指数)
main_contract = lc_contracts[lc_contracts['symbol'].str.contains('2609', na=False)]
if len(main_contract) == 0:
    main_contract = lc_contracts.iloc[-1:]
if len(main_contract) > 0:
    main_close = float(main_contract['close'].iloc[0])
    index_close = closes[-1]
    basis_pct = (main_close - index_close) / index_close * 100
    if abs(basis_pct) > 1:
        l1_details['基差'] = '5分: 基差{:.1f}%, 贴/升水明显'.format(basis_pct)
        l1_score += 5
    elif abs(basis_pct) > 0.5:
        l1_details['基差'] = '3分: 基差{:.1f}%, 偏离适中'.format(basis_pct)
        l1_score += 3
    else:
        l1_details['基差'] = '2分: 基差{:.1f}%, 基本平水'.format(basis_pct)
        l1_score += 2

# 3) 期限结构
if len(lc_contracts) > 1:
    lc_contracts_sorted = lc_contracts.copy()
    lc_contracts_sorted['month_num'] = lc_contracts_sorted['symbol'].str.extract(r'(\d{4})$').astype(int)
    lc_contracts_sorted = lc_contracts_sorted.sort_values('month_num')
    closes_ts = lc_contracts_sorted['close'].values.astype(float)
    near_price = closes_ts[0]
    far_price = closes_ts[-1]
    slope = (far_price - near_price) / near_price * 100
    if slope > 2:
        l1_details['期限结构'] = '5分: Contango结构, 斜率{:.1f}%'.format(slope)
        l1_score += 5
    elif slope > 0.5:
        l1_details['期限结构'] = '3分: 轻微Contango, 斜率{:.1f}%'.format(slope)
        l1_score += 3
    elif slope < -2:
        l1_details['期限结构'] = '5分: Backwardation结构, 斜率{:.1f}%'.format(abs(slope))
        l1_score += 5
    elif slope < -0.5:
        l1_details['期限结构'] = '3分: 轻微Backwardation, 斜率{:.1f}%'.format(abs(slope))
        l1_score += 3
    else:
        l1_details['期限结构'] = '1分: 平坦结构, 斜率{:.1f}%'.format(slope)
        l1_score += 1

# 4) 跨期Spread
if len(lc_contracts) >= 2:
    spread_near = closes_ts[0] - closes_ts[1]
    if abs(spread_near) > 2000:
        l1_details['跨期Spread'] = '4分: 近远月价差{:.0f}, 跨期机会'.format(spread_near)
        l1_score += 4
    elif abs(spread_near) > 1000:
        l1_details['跨期Spread'] = '2分: 近远月价差{:.0f}, 正常'.format(spread_near)
        l1_score += 2
    else:
        l1_details['跨期Spread'] = '1分: 近远月价差{:.0f}, 趋平'.format(spread_near)
        l1_score += 1

# 5) ROC
roc_1d = (closes[-1] - closes[-2]) / closes[-2] * 100 if n >= 2 else 0
roc_3d = (closes[-1] - closes[max(0, latest_idx-2)]) / closes[max(0, latest_idx-2)] * 100 if n >= 3 else roc_1d
if abs(roc_1d) > 2:
    l1_details['ROC'] = '5分: ROC(1d)={:.1f}%, 波动剧烈'.format(roc_1d)
    l1_score += 5
elif abs(roc_1d) > 1:
    l1_details['ROC'] = '3分: ROC(1d)={:.1f}%, 波动明显'.format(roc_1d)
    l1_score += 3
else:
    l1_details['ROC'] = '1分: ROC(1d)={:.1f}%, 波动温和'.format(roc_1d)
    l1_score += 1

# 6) %b (布林带位置)
if n >= 3:
    bb_p = min(5, n)
    sma_b = np.mean(closes[-bb_p:])
    std_b = np.std(closes[-bb_p:])
    upper = sma_b + 2*std_b
    lower = sma_b - 2*std_b
    b_val = (closes[-1]-lower)/(upper-lower) if upper!=lower else 0.5
    if b_val > 0.8:
        l1_details['%b'] = '5分: %b={:.2f}, 接近上轨'.format(b_val)
        l1_score += 5
    elif b_val < 0.2:
        l1_details['%b'] = '5分: %b={:.2f}, 接近下轨'.format(b_val)
        l1_score += 5
    elif b_val > 0.6 or b_val < 0.4:
        l1_details['%b'] = '2分: %b={:.2f}, 偏离中轨'.format(b_val)
        l1_score += 2
    else:
        l1_details['%b'] = '1分: %b={:.2f}, 中轨附近'.format(b_val)
        l1_score += 1

# 7) ATR百分位
tr = np.zeros(n)
for i in range(1, n):
    tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
atr = np.mean(tr[-min(5, n):])
atr_pct = atr / closes[-1] * 100
if atr_pct > 3:
    l1_details['ATR百分位'] = '4分: ATR%={:.1f}%, 高波动'.format(atr_pct)
    l1_score += 4
elif atr_pct > 1.5:
    l1_details['ATR百分位'] = '2分: ATR%={:.1f}%, 中波动'.format(atr_pct)
    l1_score += 2
else:
    l1_details['ATR百分位'] = '1分: ATR%={:.1f}%, 低波动'.format(atr_pct)
    l1_score += 1

# 8) MA斜率
ma_slope = (np.mean(closes[-3:]) - np.mean(closes[-6:-3])) / np.mean(closes[-6:-3]) * 100 if n >= 6 else 0
if abs(ma_slope) > 2:
    l1_details['MA斜率'] = '4分: MA斜率{:.1f}%, 趋势明确'.format(ma_slope)
    l1_score += 4
elif abs(ma_slope) > 0.5:
    l1_details['MA斜率'] = '2分: MA斜率{:.1f}%, 趋势初现'.format(ma_slope)
    l1_score += 2
else:
    l1_details['MA斜率'] = '1分: MA斜率{:.1f}%, 趋平'.format(ma_slope)
    l1_score += 1

# 9) Higher Low/Lower High
recent_h = highs[-min(5, n):]
recent_l = lows[-min(5, n):]
hh = all(recent_h[i] <= recent_h[i+1] for i in range(len(recent_h)-1)) if len(recent_h)>=3 else False
lh = all(recent_h[i] >= recent_h[i+1] for i in range(len(recent_h)-1)) if len(recent_h)>=3 else False
hl = all(recent_l[i] <= recent_l[i+1] for i in range(len(recent_l)-1)) if len(recent_l)>=3 else False
ll = all(recent_l[i] >= recent_l[i+1] for i in range(len(recent_l)-1)) if len(recent_l)>=3 else False
if hh and hl:
    l1_details['HL/LH'] = '5分: HH+HL上升通道'
    l1_score += 5
elif lh and ll:
    l1_details['HL/LH'] = '5分: LH+LL下降通道'
    l1_score += 5
else:
    l1_details['HL/LH'] = '1分: 无明显HL/LH模式'
    l1_score += 1

# 10) 量价背离
price_trend = closes[-1] - closes[0]
vol_trend = volumes[-1] - volumes[0]
if (price_trend > 0 and vol_trend < 0) or (price_trend < 0 and vol_trend > 0):
    l1_details['量价背离'] = '5分: 量价背离信号'
    l1_score += 5
elif abs(price_trend) > 1000 and vol_trend > 0:
    l1_details['量价背离'] = '3分: 放量同向, 趋势确认'
    l1_score += 3
else:
    l1_details['量价背离'] = '2分: 量价关系正常'
    l1_score += 2

l1_score = min(l1_score, 55)

# ============ 3. L2: 量价信号 (15分) ============
l2_score = 0
l2_details = {}

# CCI
tp = (highs + lows + closes) / 3
sma_tp = np.mean(tp[-min(20, n):])
mad_tp = np.mean(np.abs(tp[-min(20, n):] - sma_tp))
cci = (tp[-1] - sma_tp) / (0.015 * mad_tp) if mad_tp != 0 else 0
if cci > 100:
    l2_details['CCI'] = '4分: CCI={:.0f}, 强势突破+100'.format(cci)
    l2_score += 4
elif cci < -100:
    l2_details['CCI'] = '4分: CCI={:.0f}, 弱势突破-100'.format(cci)
    l2_score += 4
elif cci > 50:
    l2_details['CCI'] = '2分: CCI={:.0f}, 偏强'.format(cci)
    l2_score += 2
elif cci < -50:
    l2_details['CCI'] = '2分: CCI={:.0f}, 偏弱'.format(cci)
    l2_score += 2
else:
    l2_details['CCI'] = '1分: CCI={:.0f}, 中性'.format(cci)
    l2_score += 1

# Supertrend
factor = 3.0
st_dir = np.ones(n)
for i in range(1, n):
    atr_i = np.mean(tr[max(0,i-10):i+1])
    mid = (highs[i] + lows[i]) / 2
    upper_band = mid + factor * atr_i
    lower_band = mid - factor * atr_i
    if i == 1:
        st_dir[i] = -1
    else:
        if closes[i] > upper_band:
            st_dir[i] = 1
        elif closes[i] < lower_band:
            st_dir[i] = -1
        else:
            st_dir[i] = st_dir[i-1]
st_signal = '多头' if st_dir[-1] == 1 else '空头'
if n >= 4 and st_dir[-1] == 1 and st_dir[-2] == -1:
    l2_details['Supertrend'] = '4分: Supertrend翻多'
    l2_score += 4
elif n >= 4 and st_dir[-1] == -1 and st_dir[-2] == 1:
    l2_details['Supertrend'] = '4分: Supertrend翻空'
    l2_score += 4
elif st_dir[-1] == 1:
    l2_details['Supertrend'] = '2分: Supertrend持续多头'
    l2_score += 2
else:
    l2_details['Supertrend'] = '2分: Supertrend持续空头'
    l2_score += 2

# Vortex 和 HMA因数据不足跳过
l2_details['Vortex交叉'] = '0分: 数据不足(需14日)'
l2_details['HMA交叉'] = '0分: 数据不足(需20日)'

l2_score = min(l2_score, 15)

# ============ 4. L3: 结构信号 (15分) ============
l3_score = 0
l3_details = {}

# RSI
delta = np.diff(closes)
gains = np.maximum(delta, 0)
losses = -np.minimum(delta, 0)
avg_gain = np.mean(gains[-min(14, len(gains)):]) if len(gains) > 0 else 0
avg_loss = np.mean(losses[-min(14, len(losses)):]) if len(losses) > 0 else 1
rs = avg_gain / avg_loss if avg_loss != 0 else 100
rsi = 100 - 100 / (1 + rs)
if rsi > 70 or rsi < 30:
    l3_details['RSI'] = '3分: RSI={:.0f}, 极端区(超买/超卖)'.format(rsi)
    l3_score += 3
elif rsi > 55:
    l3_details['RSI'] = '5分: RSI={:.0f}, 健康多头区'.format(rsi)
    l3_score += 5
elif rsi < 45:
    l3_details['RSI'] = '5分: RSI={:.0f}, 健康空头区'.format(rsi)
    l3_score += 5
else:
    l3_details['RSI'] = '2分: RSI={:.0f}, 中性区'.format(rsi)
    l3_score += 2

# DMI方向
plus_dm = np.zeros(n)
minus_dm = np.zeros(n)
for i in range(1, n):
    up_move = highs[i] - highs[i-1]
    down_move = lows[i-1] - lows[i]
    if up_move > down_move and up_move > 0:
        plus_dm[i] = up_move
    elif down_move > up_move and down_move > 0:
        minus_dm[i] = down_move
tr_sum = np.sum(tr[-min(14, n):])
pdi = np.sum(plus_dm[-min(14, n):]) / tr_sum * 100 if tr_sum != 0 else 0
ndi = np.sum(minus_dm[-min(14, n):]) / tr_sum * 100 if tr_sum != 0 else 0
if pdi > ndi and pdi - ndi > 5:
    l3_details['DMI方向'] = '3分: +DI({:.0f})>-DI({:.0f}), 多头主导'.format(pdi, ndi)
    l3_score += 3
elif ndi > pdi and ndi - pdi > 5:
    l3_details['DMI方向'] = '3分: -DI({:.0f})>+DI({:.0f}), 空头主导'.format(ndi, pdi)
    l3_score += 3
else:
    l3_details['DMI方向'] = '1分: DMI交织, 方向不明'
    l3_score += 1

# 前高/前低突破
recent_h5 = np.max(highs[-min(5, n):])
recent_l5 = np.min(lows[-min(5, n):])
if closes[-1] > recent_h5 * 1.01:
    l3_details['前高/前低突破'] = '4分: 突破{:.0f}前高'.format(recent_h5)
    l3_score += 4
elif closes[-1] < recent_l5 * 0.99:
    l3_details['前高/前低突破'] = '4分: 跌破{:.0f}前低'.format(recent_l5)
    l3_score += 4
else:
    l3_details['前高/前低突破'] = '1分: 在{:.0f}-{:.0f}区间内'.format(recent_l5, recent_h5)
    l3_score += 1

l3_score = min(l3_score, 15)

# ============ 5. L4: 确认信号 (15分) ============
l4_score = 0
l4_details = {}

# 通道突破 (Donchian通道)
dc20_h = np.max(highs[-min(20, n):])
dc20_l = np.min(lows[-min(20, n):])
dc55_h = np.max(highs[-min(55, n):]) if n >= 5 else dc20_h
dc55_l = np.min(lows[-min(55, n):]) if n >= 5 else dc20_l
if closes[-1] > dc20_h:
    l4_details['通道突破'] = '4分: 突破DC20上轨{:.0f}'.format(dc20_h)
    l4_score += 4
elif closes[-1] < dc20_l:
    l4_details['通道突破'] = '4分: 跌破DC20下轨{:.0f}'.format(dc20_l)
    l4_score += 4
else:
    l4_details['通道突破'] = '1分: 在DC通道内({:.0f}-{:.0f})'.format(dc20_l, dc20_h)
    l4_score += 1

# 均线排列
ma3 = np.mean(closes[-3:])
ma5 = np.mean(closes[-min(5, n):])
if ma3 > ma5:
    l4_details['均线排列'] = '4分: MA3({:.0f})>MA5({:.0f}), 多头排列'.format(ma3, ma5)
    l4_score += 4
elif ma3 < ma5:
    l4_details['均线排列'] = '4分: MA3({:.0f})<MA5({:.0f}), 空头排列'.format(ma3, ma5)
    l4_score += 4
else:
    l4_details['均线排列'] = '1分: 均线交织'
    l4_score += 1

# MACD确认
alpha12 = 2/13
alpha26 = 2/27
ema12 = closes[0]
ema26 = closes[0]
for i in range(1, n):
    ema12 = closes[i]*alpha12 + ema12*(1-alpha12)
    ema26 = closes[i]*alpha26 + ema26*(1-alpha26)
dif = ema12 - ema26
dea = dif  # 简化
macd_val = 2*(dif - dea)
if dif > 0:
    l4_details['MACD确认'] = '4分: MACD多头, DIF={:.0f}'.format(dif)
    l4_score += 4
elif dif < 0:
    l4_details['MACD确认'] = '4分: MACD空头, DIF={:.0f}'.format(abs(dif))
    l4_score += 4
else:
    l4_details['MACD确认'] = '1分: MACD缠绕, DIF={:.0f}'.format(dif)
    l4_score += 1

# DC55共振
if n >= 5:
    if closes[-1] > dc55_h:
        l4_details['DC55共振'] = '3分: 突破DC55上轨{:.0f}, 共振'.format(dc55_h)
        l4_score += 3
    elif closes[-1] < dc55_l:
        l4_details['DC55共振'] = '3分: 跌破DC55下轨{:.0f}, 共振'.format(dc55_l)
        l4_score += 3
    else:
        l4_details['DC55共振'] = '0分: 无共振'
else:
    l4_details['DC55共振'] = '0分: 数据不足(需55日)'

l4_score = min(l4_score, 15)

# ============ 6. 否决信号 (-20分) ============
veto_score = 0
veto_reasons = []

# ADX<15
dx_values = []
for j in range(1, n):
    up = highs[j] - highs[j-1]
    down = lows[j-1] - lows[j]
    pdi_j = max(up, 0) if up > 0 and up > down else 0
    ndi_j = max(down, 0) if down > 0 and down > up else 0
    tr_j = max(highs[j]-lows[j], abs(highs[j]-closes[j-1]), abs(lows[j]-closes[j-1]))
    if tr_j > 0:
        pdi_v = pdi_j / tr_j * 100
        ndi_v = ndi_j / tr_j * 100
        dx = abs(pdi_v - ndi_v) / (pdi_v + ndi_v) * 100 if (pdi_v + ndi_v) > 0 else 0
        dx_values.append(dx)
adx = np.mean(dx_values[-min(14, len(dx_values)):]) if dx_values else 0
if adx < 15:
    veto_score -= 20
    veto_reasons.append('ADX={:.1f}<15, 震荡市'.format(adx))
elif adx < 20:
    veto_score -= 5
    veto_reasons.append('ADX={:.1f}<20, 趋势偏弱'.format(adx))

# RSI极端
if rsi > 80:
    veto_score -= 10
    veto_reasons.append('RSI={:.0f}>80, 超买'.format(rsi))
elif rsi < 20:
    veto_score -= 10
    veto_reasons.append('RSI={:.0f}<20, 超卖'.format(rsi))

# OI背离
oi_chg_full = (ois[-1] - ois[0]) / ois[0] * 100
if (price_trend > 0 and oi_chg_full < -5) or (price_trend < 0 and oi_chg_full > 5):
    veto_score -= 10
    veto_reasons.append('OI背离: 价涨量缩/价跌量增')

# ============ 7. 最终评分 ============
total = l1_score + l2_score + l3_score + l4_score + veto_score

# 阈值判定
if total >= 80:
    threshold = "T1"
elif total >= 60:
    threshold = "T2"
else:
    threshold = "T3"

# 趋势方向与阶段判定
price_range_pct = abs(price_trend) / closes[0] * 100 if n > 1 else 0
avg_close = np.mean(closes)

# 综合判断趋势
if total >= 30 and price_range_pct > 2 and adx >= 20:
    if closes[-1] > avg_close:
        direction = "多头"
        if cci > 100:
            stage = "主升"
        elif rsi > 55 and ma3 > ma5:
            stage = "主升"
        else:
            stage = "启动"
    else:
        direction = "空头"
        if cci < -100:
            stage = "主跌"
        elif rsi < 45 and ma3 < ma5:
            stage = "主跌"
        else:
            stage = "启动"
elif total < 30 or adx < 15:
    direction = "震荡"
    stage = "震荡"
else:
    direction = "震荡"
    stage = "震荡"

# 细化阶段调整
if rsi > 70 and direction == "多头":
    stage = "衰竭"
elif rsi < 30 and direction == "空头":
    stage = "衰竭"

# 关键价位
support = np.min(lows[-min(5, n):])
resistance = np.max(highs[-min(5, n):])

# ============ 8. 输出结构化报告 ============
print("=" * 65)
print("       碳酸锂(LC) Phase 1 技术指标分析报告")
print("=" * 65)
print()
print(f"分析日期: 2026-06-28 (最新数据截至 2026-06-26)")
print(f"数据量: {n} 个交易日 (2026-06-22 ~ 2026-06-26)")
print(f"⚠️  说明: 交易所数据源仅覆盖最近5个交易日, ")
print(f"     部分长周期指标(如14日RSI)基于有限样本计算, 仅供参考")
print()

# 最新行情
print("-" * 65)
print("【最新行情】")
print(f"  最新收盘: {closes[-1]:.1f} 元/吨")
print(f"  当日区间: {lows[-1]:.1f} ~ {highs[-1]:.1f}")
print(f"  成交量: {volumes[-1]:.0f} 手")
print(f"  持仓量: {ois[-1]:.0f} 手")
print(f"  主力合约: {main_contract['symbol'].iloc[0] if len(main_contract)>0 else 'N/A'}")
print()

# 关键指标汇总
print("-" * 65)
print("【关键指标汇总】")
print(f"  ROC(1日): {roc_1d:+.2f}%       RSI(14): {rsi:.1f}")
print(f"  ADX: {adx:.1f}                 CCI(20): {cci:.1f}")
print(f"  %b: {b_val:.3f}               ATR%: {atr_pct:.2f}%")
print(f"  MA3/MA5: {ma3:.0f}/{ma5:.0f}  DMI: +DI={pdi:.1f}, -DI={ndi:.1f}")
print(f"  Supertrend: {st_signal}")
print()

# 期限结构
print("-" * 65)
print("【期限结构】")
for i in range(len(lc_contracts_sorted)):
    row = lc_contracts_sorted.iloc[i]
    mark = " ← 主力" if i == len(lc_contracts_sorted)-1 else ""
    print(f"  {row['symbol']}: {row['close']:.1f}{mark}")
print(f"  结构形态: {'Contango' if slope>0 else 'Backwardation'} (斜率 {slope:+.2f}%)")
print()

# L1-L4 打分详情
print("-" * 65)
print("【L1 萌芽信号 (55分)】")
for k, v in l1_details.items():
    print(f"  {k}: {v}")
print(f"  >> L1合计: {l1_score}/55")
print()

print("【L2 量价信号 (15分)】")
for k, v in l2_details.items():
    print(f"  {k}: {v}")
print(f"  >> L2合计: {l2_score}/15")
print()

print("【L3 结构信号 (15分)】")
for k, v in l3_details.items():
    print(f"  {k}: {v}")
print(f"  >> L3合计: {l3_score}/15")
print()

print("【L4 确认信号 (15分)】")
for k, v in l4_details.items():
    print(f"  {k}: {v}")
print(f"  >> L4合计: {l4_score}/15")
print()

print("【否决信号 (-20分)】")
for r in veto_reasons:
    print(f"  - {r}")
print(f"  >> 否决合计: {veto_score}")
print()

# 最终结论
print("=" * 65)
print("【最终分析结论】")
print(f"  趋势方向: {direction}")
print(f"  趋势阶段: {stage}")
print(f"  L1-L4得分: {l1_score}+{l2_score}+{l3_score}+{l4_score}+({veto_score}) = {total}/100")
print(f"  阈值等级: {threshold}")
print(f"  关键价位: 支撑 {support:.0f} | 阻力 {resistance:.0f}")
print(f"  数据来源: futures-quote/futures-spread | GFEX | 2026-06-28")
print()
print("###END_TECH_ANALYSIS")
