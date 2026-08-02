"""
Phase C V2: ML特征工程（改进版）

V2改进：
1. 滞后特征：ret_1d_lag1~lag5, vol_lag等
2. 更多技术指标：MACD, Bollinger Band宽度, Keltner通道
3. 滚动统计特征：skew, kurtosis, 最大回撤
4. 品种间相关性：与板块内其他品种的相关性
5. 目标变量：截面排名（替代原始收益率）

自包含说明：本脚本已内嵌所有依赖数据，无需外部配置文件即可独立运行。
"""
import pandas as pd
import numpy as np

# ===== 自包含的产业链分类数据 =====
# 原依赖：from config import SECTORS
# 已嵌入本文件，消除外部模块依赖
SECTORS = {
    '黑色系': ['I', 'RB', 'HC', 'J', 'JM', 'SM', 'SF', 'FG', 'SA'],
    '有色金属': ['CU', 'AL', 'ZN', 'PB', 'NI', 'SN', 'SS', 'SI', 'BC', 'BR', 'NR'],
    '能源化工': ['SC', 'FU', 'LU', 'BU', 'L', 'PP', 'V', 'TA', 'MA', 'EG', 'EB', 'PG', 'PF', 'SH', 'PX', 'UR', 'SP'],
    '农产品': ['A', 'B', 'M', 'Y', 'P', 'C', 'CS', 'CF', 'SR', 'OI', 'RM', 'AP', 'CJ', 'PK', 'LH', 'JD', 'LG', 'RS', 'RI', 'BB', 'LC', 'EC'],
    '金融期货': ['IF', 'IC', 'IH', 'IM', 'T', 'TF', 'TS', 'TL'],
    '贵金属': ['AU', 'AG', 'RU', 'WR'],
}


def compute_ml_features_v2(prices, closes_adj, start_date=None, end_date=None):
    """
    构造ML特征矩阵 V2（改进版）

    参数: 与V1相同

    返回:
        feature_df: pd.DataFrame, index=MultiIndex(date, variety), columns=feature_names
        target_df: pd.DataFrame, index=MultiIndex(date, variety), columns=['target_5d']
    """
    print("[ML Feature V2] 构造ML特征矩阵（改进版）...")

    # 获取所有品种的原始数据 → 宽表格式
    varieties = [v for v in prices.keys() if 'close' in prices[v].columns]
    raw_closes = pd.DataFrame({v: prices[v]['close'] for v in varieties})
    raw_highs = pd.DataFrame({v: prices[v]['high'] for v in varieties if 'high' in prices[v].columns})
    raw_lows = pd.DataFrame({v: prices[v]['low'] for v in varieties if 'low' in prices[v].columns})
    volumes = pd.DataFrame({v: prices[v]['volume'] for v in varieties if 'volume' in prices[v].columns})
    ois = pd.DataFrame({v: prices[v].get('open_interest', prices[v].get('amount', pd.Series(dtype=float)))
                        for v in varieties if 'open_interest' in prices[v].columns or 'amount' in prices[v].columns})

    # 统一索引
    for df in [raw_closes, raw_highs, raw_lows, volumes, ois]:
        df.index = pd.to_datetime(df.index)
    closes = closes_adj.copy()
    closes.index = pd.to_datetime(closes.index)

    # 截取时间范围
    if start_date:
        cut = pd.Timestamp(start_date)
        closes = closes[closes.index >= cut]
    if end_date:
        cut = pd.Timestamp(end_date)
        closes = closes[closes.index <= cut]
    all_idx = closes.index

    # ===== 基础收益率特征 =====
    returns_1d = closes.pct_change()
    returns_5d = closes.pct_change(5)
    returns_10d = closes.pct_change(10)
    returns_20d = closes.pct_change(20)
    returns_60d = closes.pct_change(60)

    # ===== V2改进1: 滞后特征 =====
    ret_1d_lag1 = returns_1d.shift(1)
    ret_1d_lag2 = returns_1d.shift(2)
    ret_1d_lag3 = returns_1d.shift(3)
    ret_1d_lag5 = returns_1d.shift(5)
    ret_1d_lag10 = returns_1d.shift(10)
    ret_5d_lag5 = returns_5d.shift(5)

    # ===== V2改进2: 波动率特征 =====
    vol_5d = returns_1d.rolling(5).std()
    vol_10d = returns_1d.rolling(10).std()
    vol_20d = returns_1d.rolling(20).std()
    vol_60d = returns_1d.rolling(60).std()
    vol_ratio_5_20 = vol_5d / vol_20d.replace(0, np.nan)
    vol_ratio_10_60 = vol_10d / vol_60d.replace(0, np.nan)

    # ===== V2改进3: 滚动统计特征 =====
    ret_skew_20 = returns_1d.rolling(20).skew()
    ret_kurt_20 = returns_1d.rolling(20).kurt()
    # 滚动最大回撤（20天）
    roll_max_20 = closes.rolling(20).max()
    roll_dd_20 = (closes / roll_max_20 - 1)
    # 滚动夏普（20天）
    roll_sharpe_20 = returns_1d.rolling(20).mean() / vol_20d.replace(0, np.nan)
    # 上涨/下跌比率
    up_days = (returns_1d > 0).rolling(20).sum()
    down_days = (returns_1d < 0).rolling(20).sum()
    up_down_ratio = up_days / down_days.replace(0, np.nan)

    # ===== 成交量特征 =====
    vol_ratio_5d = volumes.pct_change(5)
    vol_ratio_20d = volumes.pct_change(20)
    vol_ma_5 = volumes.rolling(5).mean()
    vol_ma_20 = volumes.rolling(20).mean()
    vol_break = volumes / vol_ma_20.replace(0, np.nan)
    # 成交量趋势
    vol_ma_ratio_5_20 = vol_ma_5 / vol_ma_20.replace(0, np.nan)

    # ===== 持仓量特征 =====
    oi_change_5d = ois.pct_change(5)
    oi_change_20d = ois.pct_change(20)

    # ===== 量价相关性 =====
    vp_corr_20 = returns_1d.rolling(20).corr(volumes).fillna(0)

    # ===== V2改进4: 价格位置 =====
    high_20 = raw_highs.rolling(20).max()
    low_20 = raw_lows.rolling(20).min()
    price_range = high_20 - low_20
    pos_20 = (closes - low_20) / price_range.replace(0, np.nan)

    high_60 = raw_highs.rolling(60).max()
    low_60 = raw_lows.rolling(60).min()
    price_range_60 = high_60 - low_60
    pos_60 = (closes - low_60) / price_range_60.replace(0, np.nan)

    # ===== V2改进5: MACD =====
    def ema(series, span):
        return series.ewm(span=span, adjust=False).mean()

    ema_12 = ema(closes, 12)
    ema_26 = ema(closes, 26)
    macd = ema_12 - ema_26
    macd_signal = ema(macd, 9)
    macd_hist = macd - macd_signal

    # ===== V2改进6: Bollinger Band宽度 =====
    ma_20 = closes.rolling(20).mean()
    std_20 = closes.rolling(20).std()
    bb_position = (closes - ma_20) / (2 * std_20.replace(0, np.nan))
    bb_width = 4 * std_20 / ma_20.replace(0, np.nan)  # 标准化带宽
    bb_breakout = (closes > ma_20 + 2 * std_20).astype(float) - \
                  (closes < ma_20 - 2 * std_20).astype(float)

    # ===== RSI(14) =====
    def compute_rsi(price, window=14):
        delta = price.diff()
        gain = delta.clip(lower=0).rolling(window).mean()
        loss = (-delta.clip(upper=0)).rolling(window).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - 100 / (1 + rs)

    rsi_14 = compute_rsi(closes, 14)

    # ===== 截面相对强度 =====
    def cross_sectional_rank(df):
        return df.rank(axis=1, pct=True)

    rank_ret_5d = cross_sectional_rank(returns_5d)
    rank_ret_20d = cross_sectional_rank(returns_20d)
    rank_vol_20d = cross_sectional_rank(-vol_20d)
    rank_vol_break = cross_sectional_rank(vol_break)
    rank_pos_20 = cross_sectional_rank(pos_20)
    rank_macd_hist = cross_sectional_rank(macd_hist)
    rank_rsi_14 = cross_sectional_rank(rsi_14)

    # ===== 板块内相对强度 =====
    def sector_rank(df):
        ranked = pd.DataFrame(0.5, index=df.index, columns=df.columns)
        for sector, members in SECTORS.items():
            vars_in = [v for v in members if v in df.columns]
            if len(vars_in) < 2:
                continue
            ranked[vars_in] = df[vars_in].rank(axis=1, pct=True)
        return ranked

    sector_rank_ret_5d = sector_rank(returns_5d)
    sector_rank_ret_20d = sector_rank(returns_20d)
    sector_rank_vol_20d = sector_rank(-vol_20d)

    # ===== V2改进7: 加速度 =====
    accel_5d = returns_1d.diff(5)
    accel_10d = returns_5d.diff(2)

    # ===== V2改进8: 价格动量持续性 =====
    # 过去5天中上涨天数比例
    up_ratio_5 = (returns_1d > 0).rolling(5).mean()
    up_ratio_10 = (returns_1d > 0).rolling(10).mean()
    # 连续上涨/下跌天数
    def consecutive_up(series):
        return (series > 0).astype(int).groupby(
            (series <= 0).astype(int).cumsum()
        ).cumsum()
    def consecutive_down(series):
        return (series < 0).astype(int).groupby(
            (series >= 0).astype(int).cumsum()
        ).cumsum()

    cons_up_5 = returns_1d.apply(consecutive_up)
    cons_down_5 = returns_1d.apply(consecutive_down)

    # ===== V2改进9: 品种间相关性（板块内） =====
    # 各品种与板块内其他品种的平均相关性
    def sector_corr(df, window=20):
        result = pd.DataFrame(0.0, index=df.index, columns=df.columns)
        for sector, members in SECTORS.items():
            vars_in = [v for v in members if v in df.columns]
            if len(vars_in) < 3:
                continue
            sector_rets = df[vars_in]
            # 滚动相关性矩阵
            rolling_corr = sector_rets.rolling(window).corr()
            # 每个品种与板块内其他品种的平均相关性
            for v in vars_in:
                # 从rolling corr矩阵中提取
                others = [x for x in vars_in if x != v]
                if len(others) == 0:
                    continue
                # 用rolling corr重新计算更高效
                v_corr = sector_rets[v].rolling(window).corr(sector_rets[others].mean(axis=1))
                result[v] = v_corr.fillna(0)
        return result

    sector_corr_20 = sector_corr(returns_1d, 20)

    # ===== 收集所有特征 =====
    feature_dict = {
        # 基础收益率
        'ret_1d': returns_1d,
        'ret_5d': returns_5d,
        'ret_10d': returns_10d,
        'ret_20d': returns_20d,
        'ret_60d': returns_60d,
        # V2: 滞后特征
        'ret_lag1': ret_1d_lag1,
        'ret_lag2': ret_1d_lag2,
        'ret_lag3': ret_1d_lag3,
        'ret_lag5': ret_1d_lag5,
        'ret_lag10': ret_1d_lag10,
        'ret_5d_lag5': ret_5d_lag5,
        # 波动率
        'vol_5d': vol_5d,
        'vol_10d': vol_10d,
        'vol_20d': vol_20d,
        'vol_60d': vol_60d,
        'vol_ratio_5_20': vol_ratio_5_20,
        'vol_ratio_10_60': vol_ratio_10_60,
        # V2: 滚动统计
        'ret_skew_20': ret_skew_20,
        'ret_kurt_20': ret_kurt_20,
        'roll_dd_20': roll_dd_20,
        'roll_sharpe_20': roll_sharpe_20,
        'up_down_ratio_20': up_down_ratio,
        # 成交量
        'vol_change_5d': vol_ratio_5d,
        'vol_change_20d': vol_ratio_20d,
        'vol_breakout': vol_break,
        'vol_ma_ratio_5_20': vol_ma_ratio_5_20,
        # 持仓量
        'oi_change_5d': oi_change_5d,
        'oi_change_20d': oi_change_20d,
        # 量价
        'vp_corr_20': vp_corr_20,
        # 价格位置
        'price_pos_20': pos_20,
        'price_pos_60': pos_60,
        # V2: MACD
        'macd': macd,
        'macd_signal': macd_signal,
        'macd_hist': macd_hist,
        # V2: Bollinger
        'bb_position': bb_position,
        'bb_width': bb_width,
        'bb_breakout': bb_breakout,
        # RSI
        'rsi_14': rsi_14,
        # 截面排名
        'rank_ret_5d': rank_ret_5d,
        'rank_ret_20d': rank_ret_20d,
        'rank_vol_20d': rank_vol_20d,
        'rank_vol_break': rank_vol_break,
        'rank_pos_20': rank_pos_20,
        'rank_macd_hist': rank_macd_hist,
        'rank_rsi_14': rank_rsi_14,
        # 板块排名
        'sector_rank_ret_5d': sector_rank_ret_5d,
        'sector_rank_ret_20d': sector_rank_ret_20d,
        'sector_rank_vol_20d': sector_rank_vol_20d,
        # V2: 加速度
        'accel_5d': accel_5d,
        'accel_10d': accel_10d,
        # V2: 动量持续性
        'up_ratio_5': up_ratio_5,
        'up_ratio_10': up_ratio_10,
        'cons_up_5': cons_up_5,
        'cons_down_5': cons_down_5,
        # V2: 板块内相关性
        'sector_corr_20': sector_corr_20,
    }

    # 清理：替换inf,缩尾
    for name in feature_dict:
        df = feature_dict[name]
        df = df.replace([np.inf, -np.inf], np.nan)
        mean = df.mean().mean()
        std = df.std().mean()
        if not pd.isna(std) and std > 0:
            df = df.clip(mean - 5 * std, mean + 5 * std)
        feature_dict[name] = df

    # ===== 转换为MultiIndex格式 (date, variety) =====
    all_varieties = list(closes.columns)
    n_features = len(feature_dict)
    feature_names = list(feature_dict.keys())

    # 对齐所有特征到同一个日期索引
    common_idx = all_idx
    stacked_features = {}
    for name in feature_names:
        df = feature_dict[name]
        df_aligned = df.reindex(common_idx)
        stacked = df_aligned.stack(dropna=False)
        stacked_features[name] = stacked

    feature_df = pd.DataFrame(stacked_features)
    feature_df.index.names = ['date', 'variety']
    feature_df = feature_df.fillna(0.0)

    # 截面Z-score标准化（按日期）
    for fname in feature_names:
        date_groups = feature_df.groupby(level='date')[fname]
        mean = date_groups.transform('mean')
        std = date_groups.transform('std').replace(0, np.nan)
        feature_df[fname] = (feature_df[fname] - mean) / std
    feature_df = feature_df.fillna(0.0)

    # ===== V2改进10: 目标变量 =====
    # 使用截面排名（rank）替代原始收益率
    # 未来5天收益率 → 截面排名 (0~1)
    target_5d_raw = closes.pct_change(5).shift(-5)
    target_5d_ranked = target_5d_raw.rank(axis=1, pct=True)
    # 标准化到[-1, 1]范围
    target_5d_scaled = 2 * target_5d_ranked - 1

    target_5d_stacked = target_5d_scaled.reindex(common_idx).stack(dropna=False)
    target_df = pd.DataFrame(target_5d_stacked, columns=['target_5d'])
    target_df.index.names = ['date', 'variety']
    target_df = target_df.fillna(0.0)

    print(f"[ML Feature V2] 特征矩阵: {feature_df.shape} "
          f"({n_features}个特征, {len(common_idx)}天, {len(all_varieties)}品种)")
    return feature_df, target_df