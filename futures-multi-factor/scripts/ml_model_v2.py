"""
Phase C V2: LightGBM滚动训练（改进版）

核心改进：
1. 验证集早停：从训练数据中拆分20%作为验证集，防止过拟合
2. 降低复杂度：num_leaves=15, max_depth=4, min_data_in_leaf=200
3. 增强正则化：lambda_l1=1.0, lambda_l2=1.0, min_gain_to_split=0.1
4. 集成学习：多个不同随机种子的模型平均
5. 特征重要性追踪：记录每个窗口的特征重要性

自包含说明：本脚本已消除所有外部模块依赖，无需外部配置文件即可独立运行。
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
from datetime import datetime, timedelta


class MLFactorModelV2:
    """ML因子模型 V2：改进版滚动训练"""

    def __init__(self, train_years=3, test_years=1, lgb_params=None, n_ensemble=3):
        """
        train_years: int, 训练窗口年数
        test_years: int, 预测窗口年数
        lgb_params: dict, LightGBM参数
        n_ensemble: int, 集成模型数量（不同随机种子）
        """
        self.train_years = train_years
        self.test_years = test_years
        self.n_ensemble = n_ensemble
        self.lgb_params = lgb_params or self._default_params()
        self.models = []
        self.model_history = []
        self.feature_importance_history = []

    def _default_params(self):
        """V2改进参数：更严格的正则化，防止过拟合"""
        return {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 15,           # V1: 31 → V2: 15
            'max_depth': 4,              # V1: 6 → V2: 4
            'learning_rate': 0.03,       # V1: 0.05 → V2: 0.03
            'feature_fraction': 0.7,     # V1: 0.8 → V2: 0.7
            'bagging_fraction': 0.7,     # V1: 0.8 → V2: 0.7
            'bagging_freq': 3,           # V1: 5 → V2: 3
            'verbosity': -1,
            'num_threads': 4,
            'min_data_in_leaf': 200,     # V1: 50 → V2: 200
            'lambda_l1': 1.0,            # V1: 0.1 → V2: 1.0
            'lambda_l2': 1.0,            # V1: 0.1 → V2: 1.0
            'min_gain_to_split': 0.1,    # NEW: 最小分裂增益
            'min_sum_hessian_in_leaf': 10, # NEW: 最小叶子节点Hessian和
        }

    def _get_train_test_dates(self, all_dates):
        """生成滚动训练/测试窗口，与V1相同"""
        all_dates = sorted(all_dates)
        train_days = self.train_years * 252
        test_days = self.test_years * 252
        min_train = 126

        windows = []
        for i in range(train_days, len(all_dates) - test_days, test_days):
            train_end = all_dates[i]
            test_start = all_dates[i + 1]
            test_end = all_dates[min(i + test_days, len(all_dates) - 1)]
            train_start = all_dates[i - train_days]

            train_dates = [d for d in all_dates if train_start <= d <= train_end]
            if len(train_dates) < min_train:
                continue

            windows.append((train_start, train_end, test_start, test_end))

        return windows

    def _compute_ic(self, y_true, y_pred):
        """计算IC (Spearman rank correlation)"""
        if len(y_true) < 10:
            return 0.0
        try:
            from scipy.stats import spearmanr
            corr, _ = spearmanr(y_true, y_pred)
            return corr if not np.isnan(corr) else 0.0
        except ImportError:
            return float(np.corrcoef(
                pd.Series(y_true).rank().values,
                pd.Series(y_pred).rank().values
            )[0, 1])

    def train_rolling(self, feature_df, target_df):
        """
        滚动训练LightGBM模型（V2改进版）

        改进：
        - 训练数据中拆分20%作为验证集，用于早停
        - 多个随机种子的模型集成
        - 记录特征重要性

        返回:
            predictions: pd.Series, MultiIndex(date, variety)
            model_history: list
        """
        print("[ML Model V2] 开始滚动训练（改进版）...")
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
            train_X = feature_df.loc[train_mask].copy()
            train_y = target_df.loc[train_mask, 'target_5d'].copy()

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
            test_X = feature_df.loc[test_mask].copy()

            if len(test_X) < 100:
                print(f"    测试数据不足: {len(test_X)}行, 跳过")
                continue

            # ===== V2改进1: 从训练数据拆分验证集(20%) =====
            # 按时间顺序拆分：最后20%作为验证集（避免未来信息泄漏）
            train_dates_sorted = sorted(train_X.index.get_level_values('date').unique())
            val_cut_idx = int(len(train_dates_sorted) * 0.8)
            val_start_date = train_dates_sorted[val_cut_idx]

            val_mask = train_X.index.get_level_values('date') >= val_start_date
            train_mask_inner = train_X.index.get_level_values('date') < val_start_date

            X_train_inner = train_X.loc[train_mask_inner]
            y_train_inner = train_y.loc[train_mask_inner]
            X_val = train_X.loc[val_mask]
            y_val = train_y.loc[val_mask]

            print(f"    训练集: {len(X_train_inner)}样本, 验证集: {len(X_val)}样本")

            if len(X_val) < 100:
                print(f"    验证集数据不足: {len(X_val)}行, 用全部训练数据")
                X_train_inner = train_X
                y_train_inner = train_y
                X_val = None
                y_val = None

            # ===== V2改进2: 多个随机种子集成 =====
            ensemble_preds = []
            ensemble_models = []

            for ei in range(self.n_ensemble):
                seed = 42 + ei * 10
                params = {**self.lgb_params, 'seed': seed}

                train_data = lgb.Dataset(X_train_inner, label=y_train_inner.values)

                if X_val is not None and y_val is not None:
                    val_data = lgb.Dataset(X_val, label=y_val.values, reference=train_data)
                    valid_sets = [train_data, val_data]
                    valid_names = ['train', 'valid']
                else:
                    valid_sets = [train_data]
                    valid_names = ['train']

                model = lgb.train(
                    params,
                    train_data,
                    num_boost_round=200,
                    valid_sets=valid_sets,
                    valid_names=valid_names,
                    callbacks=[
                        lgb.early_stopping(20, first_metric_only=True),
                        lgb.log_evaluation(0),
                    ],
                )

                ensemble_models.append(model)
                pred = model.predict(test_X.values)
                ensemble_preds.append(pred)

            # 集成：平均预测值
            pred_ensemble = np.mean(ensemble_preds, axis=0)
            predictions.loc[test_mask] = pred_ensemble

            # ===== 评估 =====
            # 训练集IC
            train_pred_all = np.mean([
                m.predict(train_X.values) for m in ensemble_models
            ], axis=0)
            train_ic = self._compute_ic(train_y.values, train_pred_all)

            # 测试集IC
            window_test_ic = 0
            if len(test_X) > 5:
                try:
                    test_y = target_df.loc[test_mask, 'target_5d']
                    valid_test = test_y.notna()
                    if valid_test.sum() > 5:
                        window_test_ic = self._compute_ic(
                            test_y[valid_test].values,
                            pred_ensemble[valid_test.values]
                        )
                except Exception:
                    pass

            # ===== V2改进3: 记录特征重要性 =====
            # 取第一个模型的feature importance
            first_model = ensemble_models[0]
            if hasattr(first_model, 'feature_importance'):
                importance = first_model.feature_importance(importance_type='gain')
                feat_imp = sorted(zip(feature_names, importance),
                                  key=lambda x: x[1], reverse=True)
                top5 = [f'{n}:{v:.1f}' for n, v in feat_imp[:5]]
                print(f"    Top5特征: {', '.join(top5)}")
                self.feature_importance_history.append({
                    'window': wi + 1,
                    'importance': dict(feat_imp),
                })

            self.models.extend(ensemble_models)
            self.model_history.append({
                'window': wi + 1,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'train_samples': len(train_X),
                'test_samples': len(test_X),
                'train_ic': train_ic,
                'test_ic': window_test_ic,
                'n_features': len(feature_names),
                'n_ensemble': self.n_ensemble,
                'best_iteration': ensemble_models[0].best_iteration
                if hasattr(ensemble_models[0], 'best_iteration') else None,
            })

            print(f"    训练集IC: {train_ic:.4f}, 测试集IC: {window_test_ic:.4f}")

        # 汇总
        test_ics = [h['test_ic'] for h in self.model_history]
        avg_test_ic = np.mean(test_ics) if test_ics else 0
        print(f"\n[ML Model V2] 滚动训练完成: {len(self.models)}个模型 ({self.n_ensemble}集成)")
        print(f"  平均 Test IC: {avg_test_ic:.4f}")
        print(f"  Test IC 标准差: {np.std(test_ics):.4f}" if len(test_ics) > 1 else "")

        # 验证集早停效果统计
        best_iters = [h.get('best_iteration', 0) or 0 for h in self.model_history]
        avg_best_iter = np.mean(best_iters) if best_iters else 0
        print(f"  平均早停轮数: {avg_best_iter:.0f} (max=200)")

        self.model_history_summary = {
            'n_models': len(self.models),
            'avg_test_ic': avg_test_ic,
            'test_ics': test_ics,
            'avg_best_iteration': avg_best_iter,
        }

        return predictions, self.model_history


def train_ml_factor_v2(feature_df, target_df, train_years=3, test_years=1, n_ensemble=3):
    """
    训练ML因子 V2：改进版本

    返回:
        ml_factor: pd.Series, ML因子值
        model_history: list, 训练历史
        model: MLFactorModelV2实例
    """
    model = MLFactorModelV2(train_years=train_years, test_years=test_years, n_ensemble=n_ensemble)
    predictions, history = model.train_rolling(feature_df, target_df)
    return predictions, history, model