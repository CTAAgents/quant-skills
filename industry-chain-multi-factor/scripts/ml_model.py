"""
Phase C: LightGBM滚动训练

滚动训练策略：
- 训练窗口：3年历史数据
- 预测窗口：1年未来数据
- 目标变量：未来5天收益率（截面标准化）
- 输出：模型预测值作为ML因子

自包含说明：本脚本已消除所有外部模块依赖，无需外部配置文件即可独立运行。
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
from datetime import datetime, timedelta


class MLFactorModel:
    """ML因子模型：滚动训练LightGBM，输出预测值作为因子"""

    def __init__(self, train_years=3, test_years=1, lgb_params=None):
        """
        train_years: int, 训练窗口年数
        test_years: int, 预测窗口年数
        lgb_params: dict, LightGBM参数
        """
        self.train_years = train_years
        self.test_years = test_years
        self.lgb_params = lgb_params or self._default_params()
        self.models = []  # 保存所有滚动模型
        self.model_history = []  # 每个模型的训练信息

    def _default_params(self):
        return {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbosity': -1,
            'num_threads': 4,
            'min_data_in_leaf': 50,
            'lambda_l1': 0.1,
            'lambda_l2': 0.1,
            'max_depth': 6,
        }

    def _get_train_test_dates(self, all_dates):
        """
        生成滚动训练/测试窗口

        返回:
            windows: [(train_start, train_end, test_start, test_end), ...]
        """
        all_dates = sorted(all_dates)
        train_days = self.train_years * 252
        test_days = self.test_years * 252
        min_train = 126  # 最少半年训练数据

        windows = []
        for i in range(train_days, len(all_dates) - test_days, test_days):
            train_end = all_dates[i]
            test_start = all_dates[i + 1]
            test_end = all_dates[min(i + test_days, len(all_dates) - 1)]
            train_start = all_dates[i - train_days]

            # 确保训练数据量足够
            train_dates = [d for d in all_dates if train_start <= d <= train_end]
            if len(train_dates) < min_train:
                continue

            windows.append((train_start, train_end, test_start, test_end))

        return windows

    def train_rolling(self, feature_df, target_df):
        """
        滚动训练LightGBM模型

        参数:
            feature_df: pd.DataFrame, MultiIndex(date, variety), 特征矩阵
            target_df: pd.DataFrame, MultiIndex(date, variety), 目标变量

        返回:
            predictions: pd.Series, MultiIndex(date, variety), 模型预测值
            model_history: list, 每个训练窗口的信息
        """
        print("[ML Model] 开始滚动训练...")
        all_dates = sorted(feature_df.index.get_level_values('date').unique())
        windows = self._get_train_test_dates(all_dates)

        feature_names = [c for c in feature_df.columns]
        predictions = pd.Series(index=feature_df.index, dtype=float, name='ml_prediction')

        for wi, (train_start, train_end, test_start, test_end) in enumerate(windows):
            print(f"\n  [窗口 {wi+1}/{len(windows)}] "
                  f"训练: {train_start.date()}~{train_end.date()}, "
                  f"预测: {test_start.date()}~{test_end.date()}")

            # 训练数据
            train_mask = (feature_df.index.get_level_values('date') >= train_start) & \
                         (feature_df.index.get_level_values('date') <= train_end)
            train_X = feature_df.loc[train_mask]
            train_y = target_df.loc[train_mask, 'target_5d']

            # 去掉NaN
            valid = train_y.notna() & (train_X.sum(axis=1).notna())
            train_X = train_X.loc[valid]
            train_y = train_y.loc[valid]

            if len(train_X) < 500:
                print(f"    训练数据不足: {len(train_X)}行, 跳过")
                continue

            # 测试数据
            test_mask = (feature_df.index.get_level_values('date') >= test_start) & \
                        (feature_df.index.get_level_values('date') <= test_end)
            test_X = feature_df.loc[test_mask]

            if len(test_X) < 100:
                print(f"    测试数据不足: {len(test_X)}行, 跳过")
                continue

            # 训练模型
            train_data = lgb.Dataset(train_X, label=train_y.values)
            model = lgb.train(
                self.lgb_params,
                train_data,
                num_boost_round=200,
                valid_sets=[train_data],
                callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)],
            )

            # 预测
            pred = model.predict(test_X.values)
            predictions.loc[test_mask] = pred

            # 记录模型信息
            train_ic = np.corrcoef(train_y.values, model.predict(train_X.values))[0, 1] if len(train_y) > 5 else 0
            test_ic = 0
            if len(test_X) > 5:
                try:
                    test_y = target_df.loc[test_mask, 'target_5d']
                    valid_test = test_y.notna()
                    if valid_test.sum() > 5:
                        test_ic = np.corrcoef(test_y[valid_test].values, pred[valid_test.values])[0, 1]
                except:
                    pass

            self.models.append(model)
            self.model_history.append({
                'window': wi + 1,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'train_samples': len(train_X),
                'test_samples': len(test_X),
                'train_ic': train_ic,
                'test_ic': test_ic,
                'n_features': len(feature_names),
            })

            print(f"    训练集: {len(train_X)}样本, Train IC: {train_ic:.4f}")
            print(f"    测试集: {len(test_X)}样本, Test IC: {test_ic:.4f}")

        # 汇总
        test_ics = [h['test_ic'] for h in self.model_history]
        avg_test_ic = np.mean(test_ics) if test_ics else 0
        print(f"\n[ML Model] 滚动训练完成: {len(self.models)}个模型")
        print(f"  平均 Test IC: {avg_test_ic:.4f}")
        print(f"  Test IC 标准差: {np.std(test_ics):.4f}" if len(test_ics) > 1 else "")

        self.model_history_summary = {
            'n_models': len(self.models),
            'avg_test_ic': avg_test_ic,
            'test_ics': test_ics,
        }

        return predictions, self.model_history


def train_ml_factor(feature_df, target_df, train_years=3, test_years=1):
    """
    训练ML因子：滚动训练LightGBM，返回预测值作为因子

    返回:
        ml_factor: pd.Series, MultiIndex(date, variety), ML因子值
        model_history: list, 训练历史
        model: MLFactorModel实例
    """
    model = MLFactorModel(train_years=train_years, test_years=test_years)
    predictions, history = model.train_rolling(feature_df, target_df)
    return predictions, history, model