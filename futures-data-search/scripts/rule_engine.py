#!/usr/bin/env python3
"""
金融规则引擎
用于数据校验、合规检查和风险控制

功能：
- 数据完整性校验
- 价格逻辑检查
- 持仓量异常检测
- 交割规则校验
- 保证金计算
- 风险指标计算
"""

import re
import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum


class RuleLevel(Enum):
    """规则级别"""
    ERROR = "error"      # 错误，数据不可用
    WARNING = "warning"  # 警告，数据可能有问题
    INFO = "info"        # 信息，仅供参考


@dataclass
class ValidationResult:
    """校验结果"""
    rule_name: str
    level: RuleLevel
    passed: bool
    message: str
    details: Optional[Dict] = None


class FinancialRuleEngine:
    """金融规则引擎"""

    # 期货合约交易单位
    CONTRACT_UNITS = {
        # SHFE
        "CU": 5, "AL": 5, "ZN": 5, "PB": 5, "NI": 1, "SN": 1,
        "AU": 1000, "AG": 15, "RB": 10, "HC": 10, "SS": 5,
        "RU": 10, "BR": 5, "FU": 10, "BU": 10, "WR": 10,
        "SP": 10, "AO": 20,
        # DCE
        "A": 10, "B": 10, "M": 10, "Y": 10, "P": 10,
        "C": 10, "CS": 10, "I": 100, "J": 100, "JM": 60,
        "L": 5, "V": 5, "PP": 5, "EG": 10, "EB": 5,
        "PG": 20, "JD": 5, "LH": 16, "RR": 10,
        # CZCE
        "AP": 10, "CF": 5, "CY": 5, "CJ": 5, "FG": 20,
        "SA": 20, "SH": 30, "MA": 10, "TA": 5, "UR": 20,
        "PF": 5, "PK": 5, "OI": 10, "RM": 10, "RS": 10,
        "SR": 10, "WH": 20, "PM": 50, "SM": 5, "SF": 5,
        # GFEX
        "SI": 5, "LC": 1, "PS": 3,
        # INE
        "SC": 1000, "LU": 10, "NR": 10, "BC": 5,
        # CFFEX
        "IF": 300, "IC": 200, "IM": 200, "IH": 300,
        "T": 10000, "TF": 10000, "TS": 10000, "TL": 10000,
    }

    # 涨跌停板幅度（默认）
    LIMIT_UP_DOWN = {
        "CU": 0.06, "AL": 0.06, "ZN": 0.06, "PB": 0.06, "NI": 0.08, "SN": 0.08,
        "AU": 0.06, "AG": 0.07, "RB": 0.06, "HC": 0.06, "SS": 0.06,
        "RU": 0.06, "BR": 0.06, "FU": 0.06, "BU": 0.06,
        "I": 0.06, "J": 0.06, "JM": 0.06,
        "M": 0.06, "Y": 0.06, "P": 0.06,
        "CF": 0.06, "SR": 0.06, "MA": 0.06, "TA": 0.06,
        "SC": 0.08,
        "IF": 0.10, "IC": 0.10, "IM": 0.10, "IH": 0.10,
    }

    def __init__(self):
        pass

    def validate_quote(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """
        校验行情数据

        Args:
            data: 行情数据字典

        Returns:
            校验结果列表
        """
        results = []

        # 1. 必填字段检查
        required_fields = ['variety', 'contract', 'open', 'high', 'low', 'close', 'volume', 'open_interest']
        for field in required_fields:
            if field not in data or data[field] is None:
                results.append(ValidationResult(
                    rule_name="required_field",
                    level=RuleLevel.ERROR,
                    passed=False,
                    message=f"缺少必填字段: {field}",
                    details={"field": field}
                ))

        # 2. 价格逻辑检查
        if all(k in data for k in ['open', 'high', 'low', 'close']):
            price_results = self._validate_price_logic(data)
            results.extend(price_results)

        # 3. 成交量/持仓量检查
        if 'volume' in data and 'open_interest' in data:
            oi_results = self._validate_oi_volume(data)
            results.extend(oi_results)

        # 4. 涨跌停检查
        if 'variety' in data and 'close' in data and 'pre_close' in data:
            limit_results = self._validate_limit(data)
            results.extend(limit_results)

        return results

    def _validate_price_logic(self, data: Dict) -> List[ValidationResult]:
        """校验价格逻辑"""
        results = []

        open_price = float(data.get('open', 0))
        high_price = float(data.get('high', 0))
        low_price = float(data.get('low', 0))
        close_price = float(data.get('close', 0))

        # 非负检查
        if any(p < 0 for p in [open_price, high_price, low_price, close_price]):
            results.append(ValidationResult(
                rule_name="price_non_negative",
                level=RuleLevel.ERROR,
                passed=False,
                message="价格不能为负数",
                details={"open": open_price, "high": high_price, "low": low_price, "close": close_price}
            ))

        # high >= low
        if high_price > 0 and low_price > 0 and high_price < low_price:
            results.append(ValidationResult(
                rule_name="high_gte_low",
                level=RuleLevel.WARNING,
                passed=False,
                message="最高价应大于等于最低价",
                details={"high": high_price, "low": low_price}
            ))

        # high >= open, high >= close
        if high_price > 0:
            if open_price > 0 and high_price < open_price:
                results.append(ValidationResult(
                    rule_name="high_gte_open",
                    level=RuleLevel.WARNING,
                    passed=False,
                    message="最高价应大于等于开盘价",
                    details={"high": high_price, "open": open_price}
                ))
            if close_price > 0 and high_price < close_price:
                results.append(ValidationResult(
                    rule_name="high_gte_close",
                    level=RuleLevel.WARNING,
                    passed=False,
                    message="最高价应大于等于收盘价",
                    details={"high": high_price, "close": close_price}
                ))

        # low <= open, low <= close
        if low_price > 0:
            if open_price > 0 and low_price > open_price:
                results.append(ValidationResult(
                    rule_name="low_lte_open",
                    level=RuleLevel.WARNING,
                    passed=False,
                    message="最低价应小于等于开盘价",
                    details={"low": low_price, "open": open_price}
                ))
            if close_price > 0 and low_price > close_price:
                results.append(ValidationResult(
                    rule_name="low_lte_close",
                    level=RuleLevel.WARNING,
                    passed=False,
                    message="最低价应小于等于收盘价",
                    details={"low": low_price, "close": close_price}
                ))

        # 通过检查
        if not any(r for r in results if not r.passed):
            results.append(ValidationResult(
                rule_name="price_logic",
                level=RuleLevel.INFO,
                passed=True,
                message="价格逻辑检查通过"
            ))

        return results

    def _validate_oi_volume(self, data: Dict) -> List[ValidationResult]:
        """校验成交量和持仓量"""
        results = []

        volume = int(data.get('volume', 0))
        oi = int(data.get('open_interest', 0))

        # 非负检查
        if volume < 0:
            results.append(ValidationResult(
                rule_name="volume_non_negative",
                level=RuleLevel.ERROR,
                passed=False,
                message="成交量不能为负数",
                details={"volume": volume}
            ))

        if oi < 0:
            results.append(ValidationResult(
                rule_name="oi_non_negative",
                level=RuleLevel.ERROR,
                passed=False,
                message="持仓量不能为负数",
                details={"open_interest": oi}
            ))

        # 异常波动检查
        if 'pre_volume' in data and data['pre_volume'] > 0:
            volume_change = abs(volume - data['pre_volume']) / data['pre_volume']
            if volume_change > 5:  # 成交量变化超过500%
                results.append(ValidationResult(
                    rule_name="volume_spike",
                    level=RuleLevel.WARNING,
                    passed=False,
                    message="成交量异常波动",
                    details={"volume": volume, "pre_volume": data['pre_volume'], "change": volume_change}
                ))

        return results

    def _validate_limit(self, data: Dict) -> List[ValidationResult]:
        """校验涨跌停"""
        results = []

        variety = data.get('variety', '').upper()
        close_price = float(data.get('close', 0))
        pre_close = float(data.get('pre_close', 0))

        if variety in self.LIMIT_UP_DOWN and pre_close > 0:
            limit_pct = self.LIMIT_UP_DOWN[variety]
            change_pct = abs(close_price - pre_close) / pre_close

            if change_pct > limit_pct * 1.01:  # 允许1%误差
                results.append(ValidationResult(
                    rule_name="limit_check",
                    level=RuleLevel.WARNING,
                    passed=False,
                    message=f"涨跌幅超过限制 ({limit_pct*100:.1f}%)",
                    details={
                        "variety": variety,
                        "close": close_price,
                        "pre_close": pre_close,
                        "change_pct": change_pct,
                        "limit_pct": limit_pct
                    }
                ))

        return results

    def validate_delivery(self, data: Dict) -> List[ValidationResult]:
        """
        校验交割规则

        Args:
            data: 交割相关数据

        Returns:
            校验结果列表
        """
        results = []

        # 检查交割月份
        if 'delivery_month' in data and 'trade_date' in data:
            delivery_month = data['delivery_month']
            trade_date = datetime.strptime(data['trade_date'], '%Y-%m-%d')

            # 提取交割月
            if len(delivery_month) == 4:
                year = 2000 + int(delivery_month[:2])
                month = int(delivery_month[2:])
                delivery_date = datetime(year, month, 1)

                # 交割月前一个月开始提高保证金
                if trade_date.month == delivery_date.month - 1 or \
                   (trade_date.month == 12 and delivery_date.month == 1):
                    results.append(ValidationResult(
                        rule_name="delivery_margin",
                        level=RuleLevel.INFO,
                        passed=True,
                        message="进入交割月前一个月，保证金将提高",
                        details={"delivery_month": delivery_month}
                    ))

        return results

    def calculate_margin(
        self,
        variety: str,
        price: float,
        lots: int,
        margin_rate: float = 0.10
    ) -> Dict[str, float]:
        """
        计算保证金

        Args:
            variety: 品种代码
            price: 价格
            lots: 手数
            margin_rate: 保证金比例

        Returns:
            保证金计算结果
        """
        unit = self.CONTRACT_UNITS.get(variety, 10)
        contract_value = price * unit * lots
        margin = contract_value * margin_rate

        return {
            "variety": variety,
            "price": price,
            "lots": lots,
            "unit": unit,
            "contract_value": contract_value,
            "margin_rate": margin_rate,
            "margin": margin,
            "margin_per_lot": margin / lots if lots > 0 else 0,
        }

    def calculate_risk_metrics(self, data: List[Dict]) -> Dict[str, Any]:
        """
        计算风险指标

        Args:
            data: 历史行情数据列表

        Returns:
            风险指标
        """
        if not data or len(data) < 2:
            return {}

        # 计算收益率
        closes = [float(d['close']) for d in data]
        returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]

        # 计算波动率
        import statistics
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0

        # 计算最大回撤
        max_drawdown = 0
        peak = closes[0]
        for close in closes:
            if close > peak:
                peak = close
            drawdown = (peak - close) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 计算夏普比率（假设无风险利率为3%）
        risk_free_rate = 0.03 / 252  # 日化
        avg_return = sum(returns) / len(returns) if returns else 0
        sharpe_ratio = (avg_return - risk_free_rate) / volatility if volatility > 0 else 0

        return {
            "volatility_daily": volatility,
            "volatility_annual": volatility * (252 ** 0.5),
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "total_return": (closes[-1] - closes[0]) / closes[0] if closes[0] > 0 else 0,
            "data_points": len(data),
        }

    def check_contract_validity(self, variety: str, contract: str, trade_date: str) -> Dict[str, Any]:
        """
        检查合约有效性

        Args:
            variety: 品种代码
            contract: 合约代码
            trade_date: 交易日期

        Returns:
            有效性检查结果
        """
        result = {
            "valid": True,
            "variety": variety,
            "contract": contract,
            "trade_date": trade_date,
            "warnings": [],
        }

        # 提取合约月份
        month_match = re.search(r'(\d{4})$', contract)
        if month_match:
            contract_month = month_match.group(1)
            year = 2000 + int(contract_month[:2])
            month = int(contract_month[2:])

            # 检查是否已过交割月
            trade_dt = datetime.strptime(trade_date, '%Y-%m-%d')
            delivery_dt = datetime(year, month, 1)

            if trade_dt > delivery_dt:
                result["valid"] = False
                result["warnings"].append(f"合约 {contract} 已过交割月")

        return result

    # ==================== 时序一致性检查 ====================

    def validate_temporal_consistency(
        self, current: Dict[str, Any], previous: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        时序一致性检查（数据质量聚合评分的核心）。
        对比当日与上一交易日数据，变化超 Nσ 触发 WARNING。

        Args:
            current: 当前交易日数据 {"close": ..., "volume": ..., "oi": ..., "variety": "CU"}
            previous: 上一交易日数据

        Returns:
            校验结果列表
        """
        results = []
        variety = current.get("variety", "?")

        if not previous:
            results.append(ValidationResult(
                rule_name="temporal_consistency",
                level=RuleLevel.INFO,
                passed=True,
                message=f"{variety}: 无历史数据可对比，跳过时序检查",
            ))
            return results

        # 检查项：close, volume, open_interest
        checks = [
            ("close", "收盘价", 3.0),       # 3σ: 价格异常波动
            ("volume", "成交量", 5.0),      # 5σ: 成交量异常
            ("open_interest", "持仓量", 5.0),  # 5σ: 持仓量异常
        ]

        for field, label, sigma_threshold in checks:
            curr_val = current.get(field, 0)
            prev_val = previous.get(field, 0)

            if prev_val == 0 or curr_val == 0:
                continue

            # 计算变化率（百分比）
            change_pct = abs((curr_val - prev_val) / prev_val) * 100

            # sigma 阈值 = sigma_threshold * 基础波动率
            # 基础波动率：价格取 1%，量取 10%
            base_volatility = 0.01 if field == "close" else 0.10
            threshold = sigma_threshold * base_volatility * 100  # 转为百分比

            if change_pct > threshold:
                results.append(ValidationResult(
                    rule_name=f"temporal_{field}",
                    level=RuleLevel.WARNING,
                    passed=False,
                    message=(
                        f"{variety}: {label}异常波动 — "
                        f"当前 {curr_val}，前值 {prev_val}，变化 {change_pct:.1f}%"
                        f"（阈值 {threshold:.0f}%）"
                    ),
                    details={
                        "field": field,
                        "current": curr_val,
                        "previous": prev_val,
                        "change_pct": round(change_pct, 2),
                        "threshold": round(threshold, 1),
                    },
                ))

        # 计算聚合质量分数 (0-100)
        warnings_count = len([r for r in results if r.level == RuleLevel.WARNING])
        quality_score = max(0, 100 - warnings_count * 25)

        results.append(ValidationResult(
            rule_name="quality_score",
            level=RuleLevel.INFO,
            passed=True,
            message=f"{variety}: 数据质量评分 {quality_score}/100",
            details={"quality_score": quality_score, "total_warnings": warnings_count},
        ))

        return results


def main():
    """测试函数"""
    engine = FinancialRuleEngine()

    # 测试数据校验
    test_data = {
        "variety": "CU",
        "contract": "CU2609",
        "open": 78500,
        "high": 78950,
        "low": 78320,
        "close": 78780,
        "volume": 125000,
        "open_interest": 185000,
        "pre_close": 78200,
    }

    print("=== 数据校验测试 ===")
    results = engine.validate_quote(test_data)
    for r in results:
        print(f"  [{r.level.value}] {r.rule_name}: {r.message}")

    # 测试保证金计算
    print("\n=== 保证金计算测试 ===")
    margin = engine.calculate_margin("CU", 78780, 10, 0.10)
    print(f"  品种: {margin['variety']}")
    print(f"  价格: {margin['price']}")
    print(f"  手数: {margin['lots']}")
    print(f"  合约价值: {margin['contract_value']:,.2f}")
    print(f"  保证金: {margin['margin']:,.2f}")

    # 测试风险指标计算
    print("\n=== 风险指标测试 ===")
    historical_data = [
        {"close": 78000},
        {"close": 78500},
        {"close": 78200},
        {"close": 78800},
        {"close": 78780},
    ]
    risk = engine.calculate_risk_metrics(historical_data)
    print(f"  日波动率: {risk.get('volatility_daily', 0):.4f}")
    print(f"  年波动率: {risk.get('volatility_annual', 0):.4f}")
    print(f"  最大回撤: {risk.get('max_drawdown', 0):.4f}")
    print(f"  夏普比率: {risk.get('sharpe_ratio', 0):.4f}")


if __name__ == "__main__":
    main()
