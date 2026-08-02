"""
Phase C: ML特征工程（优化版）

从原始OHLCV数据构造ML特征矩阵，用于LightGBM训练。
完全向量化，避免Python嵌套循环。

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


def compute_ml_features(prices, closes_adj, start_date=None, end_date=None):
    """
    构造ML特征矩阵（完全向量化版本）

    参数:
        prices: dict, {variety: pd.DataFrame} 原始OHLCV数据
        closes_adj: pd.DataFrame, index=date, columns=variety, 调整后价格
        start_date: str, 回测开始日期
        end_date: str, 回测结束日期

    返回:
        feature_df: pd.DataFrame, index=MultiIndex(date, variety), columns=feature_names
        target_df: pd.DataFrame, index=MultiIndex(date, variety), columns=['target_5d']
    """
    print("[ML Feature] 构造ML特征矩阵...")

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

    # ===== 收益率特征 =====
    returns_1d = closes.pct_change()
    returns_5d = closes.pct_change(5)
    returns_10d = closes.pct_change(10)
    returns_20d = closes.pct_change(20)
    returns_60d = closes.pct_change(60)

    # ===== 波动率特征 =====
    vol_5d = returns_1d.rolling(5).std()
    vol_10d = returns_1d.rolling(10).std()
    vol_20d = returns_1d.rolling(20).std()
    vol_60d = returns_1d.rolling(60).std()
    vol_ratio_5_20 = vol_5d / vol_20d.replace(0, np.nan)
    vol_ratio_10_60 = vol_10d / vol_60d.replace(0, np.nan)

    # ===== 成交量特征 =====
    vol_ratio_5d = volumes.pct_change(5)
    vol_ratio_20d = volumes.pct_change(20)
    vol_ma_5 = volumes.rolling(5).mean()
    vol_ma_20 = volumes.rolling(20).mean()
    vol_break = volumes / vol_ma_20.replace(0, np.nan)

    # ===== 持仓量特征 =====
    oi_change_5d = ois.pct_change(5)
    oi_change_20d = ois.pct_change(20)

    # ===== 量价相关性（滚动窗口） =====
    # 用rolling corr替代手动循环
    vp_corr_20 = returns_1d.rolling(20).corr(volumes).fillna(0)

    # ===== 价格位置 =====
    high_20 = raw_highs.rolling(20).max()
    low_20 = raw_lows.rolling(20).min()
    price_range = high_20 - low_20
    pos_20 = (closes - low_20) / price_range.replace(0, np.nan)

    # ===== 截面相对强度 =====
    def cross_sectional_rank(df):
        return df.rank(axis=1, pct=True)

    rank_ret_5d = cross_sectional_rank(returns_5d)
    rank_ret_20d = cross_sectional_rank(returns_20d)
    rank_vol_20d = cross_sectional_rank(-vol_20d)
    rank_vol_break = cross_sectional_rank(vol_break)
    rank_pos_20 = cross_sectional_rank(pos_20)

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

    # ===== 价格加速度 =====
    accel = returns_1d.diff(5)

    # ===== 布林带位置 =====
    ma_20 = closes.rolling(20).mean()
    std_20 = closes.rolling(20).std()
    bb_position = (closes - ma_20) / (2 * std_20.replace(0, np.nan))

    # ===== RSI(14) =====
    def compute_rsi(price, window=14):
        delta = price.diff()
        gain = delta.clip(lower=0).rolling(window).mean()
        loss = (-delta.clip(upper=0)).rolling(window).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - 100 / (1 + rs)

    rsi_14 = compute_rsi(closes, 14)

    # ===== 收集所有特征到字典 =====
    feature_dict = {
        'ret_1d': returns_1d,
        'ret_5d': returns_5d,
        'ret_10d': returns_10d,
        'ret_20d': returns_20d,
        'ret_60d': returns_60d,
        'vol_5d': vol_5d,
        'vol_10d': vol_10d,
        'vol_20d': vol_20d,
        'vol_60d': vol_60d,
        'vol_ratio_5_20': vol_ratio_5_20,
        'vol_ratio_10_60': vol_ratio_10_60,
        'vol_change_5d': vol_ratio_5d,
        'vol_change_20d': vol_ratio_20d,
        'vol_breakout': vol_break,
        'oi_change_5d': oi_change_5d,
        'oi_change_20d': oi_change_20d,
        'vp_corr_20': vp_corr_20,
        'price_pos_20': pos_20,
        'rank_ret_5d': rank_ret_5d,
        'rank_ret_20d': rank_ret_20d,
        'rank_vol_20d': rank_vol_20d,
        'rank_vol_break': rank_vol_break,
        'rank_pos_20': rank_pos_20,
        'sector_rank_ret_5d': sector_rank_ret_5d,
        'sector_rank_ret_20d': sector_rank_ret_20d,
        'accel_5d': accel,
        'bb_position': bb_position,
        'rsi_14': rsi_14,
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
    # 用stack替代手动循环，效率提升100倍+
    all_varieties = list(closes.columns)
    n_features = len(feature_dict)
    feature_names = list(feature_dict.keys())

    # 对齐所有特征到同一个日期索引
    common_idx = all_idx
    # 先构建各特征的stacked Series
    stacked_features = {}
    for name in feature_names:
        df = feature_dict[name]
        # 对齐日期
        df_aligned = df.reindex(common_idx)
        # stack: wide → long (MultiIndex: date, variety)
        stacked = df_aligned.stack(dropna=False)
        stacked_features[name] = stacked

    # 组合为DataFrame
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

    # ===== 目标变量：未来5天收益率（截面标准化）=====
    target_5d = closes.pct_change(5).shift(-5)
    target_5d_stacked = target_5d.reindex(common_idx).stack(dropna=False)
    target_df = pd.DataFrame(target_5d_stacked, columns=['target_5d'])
    target_df.index.names = ['date', 'variety']
    target_df = target_df.fillna(0.0)

    # 目标变量截面标准化
    target_mean = target_df.groupby(level='date')['target_5d'].transform('mean')
    target_std = target_df.groupby(level='date')['target_5d'].transform('std').replace(0, np.nan)
    target_df['target_5d'] = (target_df['target_5d'] - target_mean) / target_std
    target_df = target_df.fillna(0.0)

    print(f"[ML Feature] 特征矩阵: {feature_df.shape} ({n_features}个特征, {len(common_idx)}天, {len(all_varieties)}品种)")
    return feature_df, target_df


def feature_importance_analysis(model, feature_names, top_n=20):
    """分析模型特征重要性"""
    import lightgbm as lgb
    if isinstance(model, lgb.Booster):
        importance = model.feature_importance(importance_type='gain')
        feat_imp = sorted(zip(feature_names, importance), key=lambda x: x[1], reverse=True)
        print(f"  Top {top_n} 特征重要性:")
        for name, imp in feat_imp[:top_n]:
            print(f"    {name}: {imp:.2f}")
        return feat_imp
    return []