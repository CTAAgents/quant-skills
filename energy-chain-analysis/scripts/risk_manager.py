#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险管理模块 — 止损/仓位/交易成本/极端行情预警

功能：
    1. 止损价计算（ATR法 + 固定百分比法）
    2. 仓位管理（基于账户规模 + 风险预算）
    3. 交易成本计算（手续费 + 保证金 + 滑点）
    4. 极端行情预警（价格异动 + 波动率突增）
    5. 信号时效性管理

用法：
    python risk_manager.py --symbol FU --account 300000
"""

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ========== 默认参数 ==========
DEFAULT_ACCOUNT_SIZE = 300000  # 默认账户规模30万
MAX_SINGLE_POSITION_PCT = 0.05  # 单品种最大仓位5%
MAX_TOTAL_POSITION_PCT = 0.15  # 总仓位最大15%
STOP_LOSS_ATR_MULT = 1.5  # 止损ATR倍数
TAKE_PROFIT_ATR_MULT = 3.0  # 止盈ATR倍数
MAX_LOSS_PER_TRADE_PCT = 0.02  # 单笔最大亏损2%本金
COMMISSION_RATE = 0.00012  # 手续费率万分之1.2
MARGIN_RATE = 0.12  # 保证金比例12%
SLIPPAGE_TICKS = 1  # 滑点跳数
TICK_SIZE = 1  # 最小变动价位
CONTRACT_MULTIPLIER = 10  # 合约乘数（吨/手）
SIGNAL_EXPIRY_DAYS = 3  # 信号有效期（天）
EXTREME_MOVE_PCT = 0.05  # 极端行情阈值5%
VOL_SPIKE_MULT = 2.0  # 波动率突增倍数


@dataclass
class StopLossResult:
    """止损计算结果"""
    stop_loss_price: float
    take_profit_price: float
    risk_per_lot: float  # 每手风险（元）
    reward_per_lot: float  # 每手收益（元）
    risk_reward_ratio: float  # 风险收益比
    method: str  # "atr" / "fixed_pct"


@dataclass
class PositionSizeResult:
    """仓位计算结果"""
    max_lots: int  # 最大手数
    recommended_lots: int  # 推荐手数
    margin_per_lot: float  # 每手保证金
    total_margin: float  # 总保证金
    risk_per_lot: float  # 每手风险
    total_risk: float  # 总风险
    account_pct: float  # 占账户比例


@dataclass
class TradingCostResult:
    """交易成本计算结果"""
    commission_open: float  # 开仓手续费
    commission_close: float  # 平仓手续费
    total_commission: float  # 总手续费
    margin_required: float  # 所需保证金
    slippage_cost: float  # 滑点成本
    total_cost: float  # 总成本


@dataclass
class MarketAlert:
    """市场预警"""
    alert_type: str  # "price_spike" / "vol_spike" / "limit_move"
    severity: str  # "warning" / "critical"
    message: str
    timestamp: str
    value: float
    threshold: float


@dataclass
class ArbitrageParams:
    """套利策略参数"""
    spread_name: str  # 价差名称
    entry_threshold: float  # 入场阈值（价差偏离均值的标准差倍数）
    exit_threshold: float  # 出场阈值（回归均值的程度）
    stop_loss_pct: float  # 止损百分比
    max_holding_days: int  # 最大持仓天数
    typical_spread: float  # 典型价差（元/吨）
    spread_std: float  # 价差波动标准差
    description: str


# ========== 套利策略参数配置 ==========
ARBITRAGE_STRATEGIES = {
    # 高低硫价差套利（LU-FU）
    "lu_fu_spread": ArbitrageParams(
        spread_name="LU-FU高低硫价差",
        entry_threshold=2.0,  # 价差偏离均值2倍标准差时入场
        exit_threshold=0.5,   # 回归到0.5倍标准差时止盈
        stop_loss_pct=0.03,   # 止损3%
        max_holding_days=20,  # 最大持仓20天
        typical_spread=500,   # 典型价差500元/吨
        spread_std=150,       # 标准差150元/吨
        description="LU-FU价差>800元做空价差，<200元做多价差"
    ),
    # 原油-沥青裂差套利
    "sc_bu_spread": ArbitrageParams(
        spread_name="SC-BU裂差",
        entry_threshold=2.0,
        exit_threshold=0.5,
        stop_loss_pct=0.03,
        max_holding_days=15,
        typical_spread=2000,  # 典型裂差2000元/吨
        spread_std=500,
        description="SC-BU裂差偏离均值2σ时入场，回归0.5σ时止盈"
    ),
    # 原油-燃料油裂解价差
    "fu_crack_spread": ArbitrageParams(
        spread_name="FU裂解价差",
        entry_threshold=1.5,  # 裂解价差波动较大，1.5σ即可入场
        exit_threshold=0.3,
        stop_loss_pct=0.04,   # 止损4%
        max_holding_days=25,
        typical_spread=0,     # 裂解价差可正可负
        spread_std=300,
        description="FU裂解价差>450元做空，<-450元做多"
    ),
    # 月间价差套利（近月-远月）
    "month_spread": ArbitrageParams(
        spread_name="月间价差",
        entry_threshold=2.0,
        exit_threshold=0.5,
        stop_loss_pct=0.02,
        max_holding_days=10,
        typical_spread=0,
        spread_std=100,
        description="Backwardation(近>远)做正套，Contango(远>近)做反套"
    ),
}


@dataclass
class ArbitrageSignal:
    """套利信号"""
    strategy_name: str
    direction: str  # "long_spread" / "short_spread"
    current_spread: float
    entry_spread: float
    stop_loss_spread: float
    take_profit_spread: float
    z_score: float  # 当前价差的Z分数
    signal_strength: str  # "strong" / "medium" / "weak"
    holding_days_limit: int


class RiskManager:
    """风险管理器"""

    def __init__(
        self,
        account_size: float = DEFAULT_ACCOUNT_SIZE,
        max_single_pct: float = MAX_SINGLE_POSITION_PCT,
        max_total_pct: float = MAX_TOTAL_POSITION_PCT,
        commission_rate: float = COMMISSION_RATE,
        margin_rate: float = MARGIN_RATE,
    ):
        self.account_size = account_size
        self.max_single_pct = max_single_pct
        self.max_total_pct = max_total_pct
        self.commission_rate = commission_rate
        self.margin_rate = margin_rate

    def check_arbitrage_signal(
        self,
        strategy_name: str,
        current_spread: float,
        historical_spread: pd.Series = None,
    ) -> Optional[ArbitrageSignal]:
        """检查套利信号

        Args:
            strategy_name: 策略名称（lu_fu_spread, sc_bu_spread, fu_crack_spread, month_spread）
            current_spread: 当前价差
            historical_spread: 历史价差序列（用于计算Z分数）

        Returns:
            ArbitrageSignal or None
        """
        if strategy_name not in ARBITRAGE_STRATEGIES:
            logger.warning(f"未知套利策略: {strategy_name}")
            return None

        params = ARBITRAGE_STRATEGIES[strategy_name]

        # 计算Z分数
        if historical_spread is not None and len(historical_spread) >= 20:
            mean_spread = historical_spread.mean()
            std_spread = historical_spread.std()
            z_score = (current_spread - mean_spread) / std_spread if std_spread > 0 else 0
        else:
            # 使用典型值
            mean_spread = params.typical_spread
            std_spread = params.spread_std
            z_score = (current_spread - params.typical_spread) / params.spread_std if params.spread_std > 0 else 0

        # 判断信号方向和强度
        direction = None
        signal_strength = "weak"

        if abs(z_score) >= params.entry_threshold:
            if z_score > 0:
                direction = "short_spread"  # 价差偏高，做空价差
            else:
                direction = "long_spread"  # 价差偏低，做多价差

            # 信号强度
            if abs(z_score) >= params.entry_threshold * 1.5:
                signal_strength = "strong"
            elif abs(z_score) >= params.entry_threshold * 1.2:
                signal_strength = "medium"
            else:
                signal_strength = "weak"

        if direction is None:
            return None

        # 计算入场/止损/止盈价差
        if direction == "long_spread":
            entry_spread = current_spread
            stop_loss_spread = current_spread * (1 - params.stop_loss_pct)
            take_profit_spread = mean_spread + params.exit_threshold * std_spread
        else:
            entry_spread = current_spread
            stop_loss_spread = current_spread * (1 + params.stop_loss_pct)
            take_profit_spread = mean_spread - params.exit_threshold * std_spread

        return ArbitrageSignal(
            strategy_name=strategy_name,
            direction=direction,
            current_spread=current_spread,
            entry_spread=round(entry_spread, 1),
            stop_loss_spread=round(stop_loss_spread, 1),
            take_profit_spread=round(take_profit_spread, 1),
            z_score=round(z_score, 2),
            signal_strength=signal_strength,
            holding_days_limit=params.max_holding_days,
        )

    def format_arbitrage_report(self, signals: list[ArbitrageSignal]) -> str:
        """格式化套利信号报告"""
        if not signals:
            return "无套利信号"

        lines = [
            "=" * 60,
            "  套利信号报告",
            "=" * 60,
        ]

        for sig in signals:
            params = ARBITRAGE_STRATEGIES.get(sig.strategy_name)
            dir_cn = "做多价差" if sig.direction == "long_spread" else "做空价差"
            strength_cn = {"strong": "强", "medium": "中", "weak": "弱"}[sig.signal_strength]

            lines.append(f"\n  {params.spread_name if params else sig.strategy_name}")
            lines.append(f"  方向: {dir_cn} ({strength_cn})")
            lines.append(f"  当前价差: {sig.current_spread:.1f}")
            lines.append(f"  Z分数: {sig.z_score}")
            lines.append(f"  入场价差: {sig.entry_spread:.1f}")
            lines.append(f"  止损价差: {sig.stop_loss_spread:.1f}")
            lines.append(f"  止盈价差: {sig.take_profit_spread:.1f}")
            lines.append(f"  最大持仓: {sig.holding_days_limit}天")
            if params:
                lines.append(f"  说明: {params.description}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def calculate_stop_loss(
        self,
        entry_price: float,
        direction: str,  # "long" / "short"
        atr: float,
        method: str = "atr",
        fixed_pct: float = 0.02,
    ) -> StopLossResult:
        """计算止损止盈价格"""
        if method == "atr":
            risk_amount = atr * STOP_LOSS_ATR_MULT
            reward_amount = atr * TAKE_PROFIT_ATR_MULT
        else:
            risk_amount = entry_price * fixed_pct
            reward_amount = entry_price * fixed_pct * 2

        if direction == "long":
            stop_loss = entry_price - risk_amount
            take_profit = entry_price + reward_amount
        else:
            stop_loss = entry_price + risk_amount
            take_profit = entry_price - reward_amount

        risk_per_lot = risk_amount * CONTRACT_MULTIPLIER
        reward_per_lot = reward_amount * CONTRACT_MULTIPLIER
        rr_ratio = reward_per_lot / risk_per_lot if risk_per_lot > 0 else 0

        return StopLossResult(
            stop_loss_price=round(stop_loss, 1),
            take_profit_price=round(take_profit, 1),
            risk_per_lot=round(risk_per_lot, 1),
            reward_per_lot=round(reward_per_lot, 1),
            risk_reward_ratio=round(rr_ratio, 2),
            method=method,
        )

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        direction: str,
        existing_positions: int = 0,
    ) -> PositionSizeResult:
        """计算仓位大小"""
        # 每手保证金
        margin_per_lot = entry_price * CONTRACT_MULTIPLIER * self.margin_rate

        # 每手风险（元）
        risk_per_lot = abs(entry_price - stop_loss_price) * CONTRACT_MULTIPLIER

        # 基于风险预算的最大手数（单笔最大亏损2%本金）
        max_risk_lots = int(self.account_size * MAX_LOSS_PER_TRADE_PCT / risk_per_lot) if risk_per_lot > 0 else 0

        # 基于保证金的最大手数（单品种最大仓位5%）
        max_margin_lots = int(self.account_size * self.max_single_pct / margin_per_lot) if margin_per_lot > 0 else 0

        # 取较小值
        max_lots = min(max_risk_lots, max_margin_lots)

        # 推荐手数（风险预算的一半）
        recommended_lots = max(1, max_lots // 2)

        # 总保证金和风险
        total_margin = recommended_lots * margin_per_lot
        total_risk = recommended_lots * risk_per_lot
        account_pct = total_margin / self.account_size * 100

        return PositionSizeResult(
            max_lots=max_lots,
            recommended_lots=recommended_lots,
            margin_per_lot=round(margin_per_lot, 1),
            total_margin=round(total_margin, 1),
            risk_per_lot=round(risk_per_lot, 1),
            total_risk=round(total_risk, 1),
            account_pct=round(account_pct, 2),
        )

    def calculate_trading_cost(
        self,
        entry_price: float,
        exit_price: float,
        lots: int,
    ) -> TradingCostResult:
        """计算交易成本"""
        # 手续费
        commission_open = entry_price * CONTRACT_MULTIPLIER * lots * self.commission_rate
        commission_close = exit_price * CONTRACT_MULTIPLIER * lots * self.commission_rate
        total_commission = commission_open + commission_close

        # 保证金
        margin_required = entry_price * CONTRACT_MULTIPLIER * lots * self.margin_rate

        # 滑点成本
        slippage_cost = SLIPPAGE_TICKS * TICK_SIZE * CONTRACT_MULTIPLIER * lots

        total_cost = total_commission + slippage_cost

        return TradingCostResult(
            commission_open=round(commission_open, 2),
            commission_close=round(commission_close, 2),
            total_commission=round(total_commission, 2),
            margin_required=round(margin_required, 1),
            slippage_cost=round(slippage_cost, 1),
            total_cost=round(total_cost, 2),
        )

    def check_extreme_market(
        self,
        current_price: float,
        prev_close: float,
        current_atr: float,
        historical_atr: float,
    ) -> list[MarketAlert]:
        """检查极端行情"""
        alerts = []

        # 价格异动检测
        price_change_pct = abs(current_price - prev_close) / prev_close if prev_close > 0 else 0
        if price_change_pct > EXTREME_MOVE_PCT:
            severity = "critical" if price_change_pct > 0.08 else "warning"
            alerts.append(MarketAlert(
                alert_type="price_spike",
                severity=severity,
                message=f"价格异动: {price_change_pct*100:.1f}% (阈值{EXTREME_MOVE_PCT*100}%)",
                timestamp=datetime.now().isoformat(),
                value=price_change_pct,
                threshold=EXTREME_MOVE_PCT,
            ))

        # 波动率突增检测
        if historical_atr > 0 and current_atr > historical_atr * VOL_SPIKE_MULT:
            severity = "critical" if current_atr > historical_atr * 3 else "warning"
            alerts.append(MarketAlert(
                alert_type="vol_spike",
                severity=severity,
                message=f"波动率突增: ATR {current_atr:.1f} vs 历史 {historical_atr:.1f} ({current_atr/historical_atr:.1f}x)",
                timestamp=datetime.now().isoformat(),
                value=current_atr,
                threshold=historical_atr * VOL_SPIKE_MULT,
            ))

        # 涨跌停检测（国内期货涨跌停板通常3-10%）
        if price_change_pct > 0.03:
            alerts.append(MarketAlert(
                alert_type="limit_move",
                severity="critical",
                message=f"接近涨跌停板: {price_change_pct*100:.1f}%",
                timestamp=datetime.now().isoformat(),
                value=price_change_pct,
                threshold=0.03,
            ))

        return alerts

    def check_signal_timeliness(
        self,
        signal_date: str,
        current_date: str,
    ) -> dict:
        """检查信号时效性"""
        try:
            sig_dt = datetime.strptime(signal_date, "%Y-%m-%d")
            cur_dt = datetime.strptime(current_date, "%Y-%m-%d")
            days_elapsed = (cur_dt - sig_dt).days

            if days_elapsed > SIGNAL_EXPIRY_DAYS * 2:
                status = "expired"
                message = f"信号已过期（{days_elapsed}天），建议重新评估"
            elif days_elapsed > SIGNAL_EXPIRY_DAYS:
                status = "aging"
                message = f"信号老化（{days_elapsed}天），注意风险"
            else:
                status = "fresh"
                message = f"信号有效（{days_elapsed}天）"

            return {
                "status": status,
                "days_elapsed": days_elapsed,
                "expiry_days": SIGNAL_EXPIRY_DAYS,
                "message": message,
            }
        except ValueError:
            return {"status": "unknown", "message": "日期格式错误"}

    def generate_risk_report(
        self,
        symbol: str,
        entry_price: float,
        direction: str,
        atr: float,
        signal_date: str,
    ) -> str:
        """生成完整风险管理报告"""
        # 止损计算
        sl = self.calculate_stop_loss(entry_price, direction, atr)

        # 仓位计算
        pos = self.calculate_position_size(entry_price, sl.stop_loss_price, direction)

        # 交易成本
        cost = self.calculate_trading_cost(entry_price, entry_price * 1.01, pos.recommended_lots)

        # 信号时效
        timeliness = self.check_signal_timeliness(signal_date, datetime.now().strftime("%Y-%m-%d"))

        dir_cn = "做多" if direction == "long" else "做空"
        lines = [
            "=" * 60,
            f"  {symbol} 风险管理报告（{dir_cn}）",
            "=" * 60,
            f"  入场价: {entry_price:.1f}",
            f"  ATR(14): {atr:.1f}",
            "",
            "  ── 止损止盈 ──",
            f"  止损价: {sl.stop_loss_price:.1f} (风险{sl.risk_per_lot:.0f}元/手)",
            f"  止盈价: {sl.take_profit_price:.1f} (收益{sl.reward_per_lot:.0f}元/手)",
            f"  风险收益比: 1:{sl.risk_reward_ratio}",
            "",
            "  ── 仓位建议 ──",
            f"  账户规模: {self.account_size:,.0f}元",
            f"  最大手数: {pos.max_lots}手",
            f"  推荐手数: {pos.recommended_lots}手",
            f"  每手保证金: {pos.margin_per_lot:,.0f}元",
            f"  总保证金: {pos.total_margin:,.0f}元 (占账户{pos.account_pct:.1f}%)",
            f"  总风险: {pos.total_risk:,.0f}元",
            "",
            "  ── 交易成本 ──",
            f"  手续费(开+平): {cost.total_commission:.2f}元",
            f"  滑点成本: {cost.slippage_cost:.1f}元",
            f"  总成本: {cost.total_cost:.2f}元",
            "",
            "  ── 信号时效 ──",
            f"  信号日期: {signal_date}",
            f"  状态: {timeliness['message']}",
            "=" * 60,
        ]
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="风险管理模块")
    parser.add_argument("--symbol", type=str, default="FU", help="品种代码")
    parser.add_argument("--account", type=float, default=DEFAULT_ACCOUNT_SIZE, help="账户规模")
    parser.add_argument("--price", type=float, help="入场价格")
    parser.add_argument("--atr", type=float, help="ATR值")
    parser.add_argument("--direction", type=str, default="long", choices=["long", "short"])
    args = parser.parse_args()

    rm = RiskManager(account_size=args.account)

    if args.price and args.atr:
        report = rm.generate_risk_report(
            symbol=args.symbol,
            entry_price=args.price,
            direction=args.direction,
            atr=args.atr,
            signal_date=datetime.now().strftime("%Y-%m-%d"),
        )
        print(report)
    else:
        print("用法: python risk_manager.py --symbol FU --price 3000 --atr 50 --direction long --account 300000")


if __name__ == "__main__":
    main()
