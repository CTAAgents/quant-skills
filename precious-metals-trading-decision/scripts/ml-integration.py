"""
贵金属交易决策辅助系统 - 机器学习集成模块
使用ML模型优化Regime诊断和策略匹配
"""

import json
import numpy as np
from datetime import datetime, timedelta

class MLIntegration:
    def __init__(self):
        self.regime_model = None
        self.strategy_model = None
        self.feature_names = [
            "tips_10y", "tips_10y_prev", "tips_trend",
            "dxy", "dxy_prev", "dxy_trend",
            "sofr", "sofr_change",
            "gvx", "gvx_percentile",
            "vxslv", "vxslv_percentile",
            "gold_price", "gold_200ma", "gold_above_200ma",
            "cftc_net_long", "cftc_percentile",
            "cb_purchasing", "geopolitical",
            "industrial_demand", "catalyst_demand",
            "volume_ratio", "oi_change",
            "ma20", "ma60", "ma20_above_ma60",
            "neckline_break", "pattern_head_shoulder"
        ]

    def generate_training_data(self, n_samples=1000):
        """生成训练数据"""
        np.random.seed(42)

        X = np.random.randn(n_samples, len(self.feature_names))
        y_regime = np.random.choice([0, 1, 2, 3, 4], n_samples)  # R1=0, R2=1, R3=2, R4=3, R5=4
        y_strategy = np.random.choice([0, 1, 2, 3, 4, 5, 6, 7], n_samples)  # 8种策略

        return X, y_regime, y_strategy

    def train_regime_model(self, X, y):
        """训练Regime诊断模型"""
        # 简化的决策树实现
        self.regime_model = DecisionTreeClassifier(max_depth=5)
        self.regime_model.fit(X, y)

        return self.regime_model

    def train_strategy_model(self, X, y):
        """训练策略匹配模型"""
        # 简化的决策树实现
        self.strategy_model = DecisionTreeClassifier(max_depth=5)
        self.strategy_model.fit(X, y)

        return self.strategy_model

    def predict_regime(self, features):
        """预测Regime"""
        if self.regime_model is None:
            return None

        return self.regime_model.predict(features)

    def predict_strategy(self, features):
        """预测策略"""
        if self.strategy_model is None:
            return None

        return self.strategy_model.predict(features)

    def extract_features(self, market_data):
        """提取特征"""
        features = []

        # TIPS特征
        tips_10y = market_data.get("tips_10y", 2.0)
        tips_10y_prev = market_data.get("tips_10y_prev", 2.0)
        tips_trend = tips_10y - tips_10y_prev
        features.extend([tips_10y, tips_10y_prev, tips_trend])

        # DXY特征
        dxy = market_data.get("dxy", 103)
        dxy_prev = market_data.get("dxy_prev", 103)
        dxy_trend = dxy - dxy_prev
        features.extend([dxy, dxy_prev, dxy_trend])

        # SOFR特征
        sofr = market_data.get("sofr", 5.0)
        sofr_change = market_data.get("sofr_change", 0)
        features.extend([sofr, sofr_change])

        # 波动率特征
        gvx = market_data.get("gvx", 20)
        gvx_percentile = market_data.get("gvx_percentile", 50)
        vxslv = market_data.get("vxslv", 25)
        vxslv_percentile = market_data.get("vxslv_percentile", 50)
        features.extend([gvx, gvx_percentile, vxslv, vxslv_percentile])

        # 价格特征
        gold_price = market_data.get("gold_price", 3300)
        gold_200ma = market_data.get("gold_200ma", 3200)
        gold_above_200ma = 1 if gold_price > gold_200ma else 0
        features.extend([gold_price, gold_200ma, gold_above_200ma])

        # CFTC特征
        cftc_net_long = market_data.get("cftc_net_long", 180000)
        cftc_percentile = market_data.get("cftc_percentile", 50)
        features.extend([cftc_net_long, cftc_percentile])

        # 央行购金特征
        cb_purchasing = 1 if market_data.get("cb_purchasing", False) else 0
        geopolitical = 1 if market_data.get("geopolitical", False) else 0
        features.extend([cb_purchasing, geopolitical])

        # 工业需求特征
        industrial_demand = 1 if market_data.get("industrial_demand") == "strong" else 0
        catalyst_demand = 1 if market_data.get("catalyst_demand") == "strong" else 0
        features.extend([industrial_demand, catalyst_demand])

        # 技术指标特征
        volume_ratio = market_data.get("volume_ratio", 1.0)
        oi_change = market_data.get("oi_change", 0)
        features.extend([volume_ratio, oi_change])

        # 均线特征
        ma20 = market_data.get("ma20", 3300)
        ma60 = market_data.get("ma60", 3280)
        ma20_above_ma60 = 1 if ma20 > ma60 else 0
        features.extend([ma20, ma60, ma20_above_ma60])

        # 技术形态特征
        neckline_break = 1 if market_data.get("neckline_break", False) else 0
        pattern_head_shoulder = 1 if market_data.get("pattern") in ["头肩底", "头肩顶"] else 0
        features.extend([neckline_break, pattern_head_shoulder])

        return np.array(features).reshape(1, -1)

class DecisionTreeClassifier:
    """简化的决策树分类器"""

    def __init__(self, max_depth=5):
        self.max_depth = max_depth
        self.tree = None

    def fit(self, X, y):
        """训练模型"""
        self.tree = self._build_tree(X, y, depth=0)

    def _build_tree(self, X, y, depth):
        """构建决策树"""
        n_samples, n_features = X.shape
        n_classes = len(np.unique(y))

        # 终止条件
        if depth >= self.max_depth or n_classes == 1 or n_samples < 2:
            return {"type": "leaf", "class": np.bincount(y).argmax() if len(y) > 0 else 0}

        # 找到最佳分割点
        best_feature, best_threshold = self._find_best_split(X, y)

        if best_feature is None:
            return {"type": "leaf", "class": np.bincount(y).argmax() if len(y) > 0 else 0}

        # 分割数据
        left_mask = X[:, best_feature] <= best_threshold
        right_mask = ~left_mask

        # 递归构建子树
        left_tree = self._build_tree(X[left_mask], y[left_mask], depth + 1)
        right_tree = self._build_tree(X[right_mask], y[right_mask], depth + 1)

        return {
            "type": "node",
            "feature": best_feature,
            "threshold": best_threshold,
            "left": left_tree,
            "right": right_tree
        }

    def _find_best_split(self, X, y):
        """找到最佳分割点"""
        n_samples, n_features = X.shape
        best_gini = float('inf')
        best_feature = None
        best_threshold = None

        for feature in range(n_features):
            thresholds = np.unique(X[:, feature])
            for threshold in thresholds:
                left_mask = X[:, feature] <= threshold
                right_mask = ~left_mask

                if np.sum(left_mask) == 0 or np.sum(right_mask) == 0:
                    continue

                gini = self._calculate_gini(y[left_mask], y[right_mask])

                if gini < best_gini:
                    best_gini = gini
                    best_feature = feature
                    best_threshold = threshold

        return best_feature, best_threshold

    def _calculate_gini(self, left_y, right_y):
        """计算基尼系数"""
        def gini(y):
            if len(y) == 0:
                return 0
            classes, counts = np.unique(y, return_counts=True)
            probabilities = counts / len(y)
            return 1 - np.sum(probabilities ** 2)

        n_left = len(left_y)
        n_right = len(right_y)
        n_total = n_left + n_right

        return (n_left / n_total) * gini(left_y) + (n_right / n_total) * gini(right_y)

    def predict(self, X):
        """预测"""
        if self.tree is None:
            return None

        return np.array([self._predict_single(x, self.tree) for x in X])

    def _predict_single(self, x, tree):
        """预测单个样本"""
        if tree["type"] == "leaf":
            return tree["class"]

        if x[tree["feature"]] <= tree["threshold"]:
            return self._predict_single(x, tree["left"])
        else:
            return self._predict_single(x, tree["right"])

def test_ml_integration():
    """测试机器学习集成"""
    print("\n" + "="*80)
    print("机器学习集成测试")
    print("="*80)

    ml = MLIntegration()

    # 生成训练数据
    print("\n1. 生成训练数据...")
    X, y_regime, y_strategy = ml.generate_training_data(1000)
    print(f"  训练样本数: {X.shape[0]}")
    print(f"  特征数: {X.shape[1]}")
    print(f"  Regime类别: {np.unique(y_regime)}")
    print(f"  策略类别: {np.unique(y_strategy)}")

    # 训练Regime诊断模型
    print("\n2. 训练Regime诊断模型...")
    regime_model = ml.train_regime_model(X, y_regime)
    print(f"  模型类型: {type(regime_model).__name__}")

    # 训练策略匹配模型
    print("\n3. 训练策略匹配模型...")
    strategy_model = ml.train_strategy_model(X, y_strategy)
    print(f"  模型类型: {type(strategy_model).__name__}")

    # 测试预测
    print("\n4. 测试预测...")
    test_market_data = {
        "tips_10y": 1.8,
        "tips_10y_prev": 2.0,
        "dxy": 100.5,
        "dxy_prev": 102.0,
        "sofr": 5.0,
        "sofr_change": 0,
        "gvx": 12,
        "gvx_percentile": 20,
        "vxslv": 18,
        "vxslv_percentile": 22,
        "gold_price": 3350,
        "gold_200ma": 3200,
        "cftc_net_long": 200000,
        "cftc_percentile": 60,
        "cb_purchasing": True,
        "geopolitical": False,
        "industrial_demand": "strong",
        "volume_ratio": 1.5,
        "oi_change": 2000,
        "ma20": 3300,
        "ma60": 3280,
        "neckline_break": False,
        "pattern": None
    }

    features = ml.extract_features(test_market_data)
    print(f"  特征向量形状: {features.shape}")

    regime_pred = ml.predict_regime(features)
    strategy_pred = ml.predict_strategy(features)
    print(f"  预测Regime: {regime_pred}")
    print(f"  预测策略: {strategy_pred}")

    return ml

if __name__ == "__main__":
    test_ml_integration()
