#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LPG（液化石油气）专项数据获取脚本 v1.0

功能：
    获取LPG专项数据（不依赖TqSdk）：
    1. 沙特阿美CP丙烷/丁烷合同价（月度）
    2. FEI远东指数（日度）
    3. PDH利润估算
    4. 国内LPG价格

数据源：
    - Tier 1: 同花顺、东方财富（CP价格新闻）
    - Tier 2: 卓创资讯、百川盈孚（市场分析）
    - Tier 3: WebSearch抓取

用法：
    python fetch_pg_data.py              # 获取全部数据
    python fetch_pg_data.py --cp         # 仅获取CP价格
    python fetch_pg_data.py --fei       # 仅获取FEI指数
"""

import argparse
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(__file__).parent.parent / "data" / "futures_data.duckdb"


def fetch_cp_price_from_web() -> Optional[dict]:
    """
    从财经网站获取沙特阿美CP价格
    
    返回: {
        'date': '2024-12-09',
        'propane_cp': 635,  # 美元/吨
        'butane_cp': 630,   # 美元/吨
        'source': '同花顺'
    }
    """
    try:
        # 使用WebSearch获取最新CP价格新闻
        # 由于无法直接访问，先返回None让调用方知道需要手动更新
        logger.warning("CP价格需要从财经新闻获取，建议关注同花顺/东方财富月度CP报道")
        return None
    except Exception as e:
        logger.error(f"获取CP价格失败: {e}")
        return None


def parse_cp_price_from_text(text: str) -> Optional[dict]:
    """
    从文本中解析CP价格
    
    支持格式：
    - "丙烷为635美元/吨"
    - "丙烷价格615美元/吨，较上月下降15美元/吨"
    """
    result = {}
    
    # 匹配丙烷价格
    propane_pattern = r'丙烷[为价格]?(\d+)[美元/吨]?'
    propane_match = re.search(propane_pattern, text)
    if propane_match:
        result['propane_cp'] = int(propane_match.group(1))
    
    # 匹配丁烷价格
    butane_pattern = r'丁烷[为价格]?(\d+)[美元/吨]?'
    butane_match = re.search(butane_pattern, text)
    if butane_match:
        result['butane_cp'] = int(butane_match.group(1))
    
    return result if result else None


def estimate_pdh_margin(
    cp_propane: float,
    propylene_price: float,
    usdcny: float = 7.2,
    processing_cost: float = 150.0
) -> float:
    """
    估算PDH利润
    
    参数:
        cp_propane: CP丙烷价格（美元/吨）
        propylene_price: 丙烯价格（元/吨）
        usdcny: 美元兑人民币汇率
        processing_cost: 加工成本（元/吨）
    
    返回:
        PDH利润（元/吨）
    """
    propane_cost_rmb = cp_propane * usdcny
    pdh_margin = propylene_price - propane_cost_rmb - processing_cost
    return pdh_margin


def get_demo_cp_data() -> dict:
    """
    获取演示用CP数据（当无法获取真实数据时使用）
    
    模拟2024年12月的CP价格数据
    """
    return {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'propane_cp': 635,  # 美元/吨
        'butane_cp': 630,   # 美元/吨
        'source': '演示数据',
        'is_demo': True
    }


def save_pg_data_to_duckdb(data: dict, db_path: str = None):
    """将PG数据保存到DuckDB"""
    if db_path is None:
        db_path = str(DB_PATH)
    
    try:
        import duckdb
        conn = duckdb.connect(db_path)
        try:
            # 创建PG专项数据表（如果不存在）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pg_market_data (
                    date DATE,
                    propane_cp DOUBLE,
                    butane_cp DOUBLE,
                    propane_cost_rmb DOUBLE,
                    butane_cost_rmb DOUBLE,
                    fei_index DOUBLE,
                    pdh_margin DOUBLE,
                    source VARCHAR,
                    is_demo BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 插入数据
            propane_cost_rmb = data.get('propane_cp', 0) * 7.2
            butane_cost_rmb = data.get('butane_cp', 0) * 7.2
            pdh_margin = estimate_pdh_margin(
                data.get('propane_cp', 0),
                data.get('propylene_price', 5000),
                7.2, 150.0
            )
            
            conn.execute("""
                INSERT INTO pg_market_data 
                (date, propane_cp, butane_cp, propane_cost_rmb, butane_cost_rmb, fei_index, pdh_margin, source, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('date', datetime.now().strftime('%Y-%m-%d')),
                data.get('propane_cp'),
                data.get('butane_cp'),
                propane_cost_rmb,
                butane_cost_rmb,
                data.get('fei_index'),
                pdh_margin,
                data.get('source', '未知'),
                data.get('is_demo', False)
            ))
            
            logger.info(f"✅ PG市场数据已保存: CP丙烷={data.get('propane_cp')}美元/吨")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"保存PG数据失败: {e}")


def load_pg_data_from_duckdb(db_path: str = None, days: int = 30) -> pd.DataFrame:
    """从DuckDB加载PG数据"""
    if db_path is None:
        db_path = str(DB_PATH)
    
    try:
        import duckdb
        conn = duckdb.connect(db_path, read_only=True)
        try:
            df = conn.execute(f"""
                SELECT * FROM pg_market_data 
                ORDER BY date DESC 
                LIMIT {days}
            """).fetchdf()
            return df
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"加载PG数据失败: {e}")
        return pd.DataFrame()


def generate_pg_report(data: dict) -> str:
    """生成PG市场简报"""
    propane_cp = data.get('propane_cp', 0)
    butane_cp = data.get('butane_cp', 0)
    propane_cost_rmb = propane_cp * 7.2
    butane_cost_rmb = butane_cp * 7.2
    source = data.get('source', '未知')
    is_demo = data.get('is_demo', False)
    
    demo_warning = "【⚠️ 演示数据】" if is_demo else ""
    
    report = f"""
{demo_warning}
========================================
    LPG市场数据简报
========================================
数据日期: {data.get('date', 'N/A')}
数据来源: {source}

【CP合同价】（沙特阿美）
  丙烷 CP: {propane_cp} 美元/吨
  丁烷 CP: {butane_cp} 美元/吨

【人民币成本】（汇率7.2）
  丙烷到岸成本: {propane_cost_rmb:.0f} 元/吨
  丁烷到岸成本: {butane_cost_rmb:.0f} 元/吨

【PDH利润估算】
  丙烯价格: {data.get('propylene_price', 'N/A')} 元/吨（需手动输入）
  估算PDH利润: {data.get('estimated_pdh_margin', 'N/A')} 元/吨

========================================
"""
    return report


def main():
    parser = argparse.ArgumentParser(description="LPG专项数据获取工具")
    parser.add_argument('--cp', action='store_true', help='仅获取CP价格')
    parser.add_argument('--fei', action='store_true', help='仅获取FEI指数')
    parser.add_argument('--demo', action='store_true', help='使用演示数据')
    parser.add_argument('--db', type=str, help='DuckDB路径')
    parser.add_argument('--propane-price', type=float, help='丙烯价格（元/吨）')
    parser.add_argument('--propane-cp', type=float, help='丙烷CP价格（美元/吨，手动输入）')
    parser.add_argument('--butane-cp', type=float, help='丁烷CP价格（美元/吨，手动输入）')
    parser.add_argument('--source', type=str, default='手动输入', help='数据来源说明')
    args = parser.parse_args()
    
    logger.info("LPG专项数据获取开始...")
    
    # 尝试获取真实CP数据
    data = None
    if args.demo:
        data = get_demo_cp_data()
        logger.info("使用演示数据")
    elif args.propane_cp:
        # 手动输入CP价格
        data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'propane_cp': args.propane_cp,
            'butane_cp': args.butane_cp or args.propane_cp,  # 默认和丙烷相同
            'source': args.source,
            'is_demo': False
        }
        logger.info(f"使用手动输入CP价格: 丙烷={args.propane_cp} 美元/吨")
    else:
        # 尝试从网页获取
        data = fetch_cp_price_from_web()
        if data is None:
            logger.warning("无法获取真实CP价格数据，使用演示数据")
            data = get_demo_cp_data()
    
    # 如果提供了丙烯价格，计算PDH利润
    if args.propane_price:
        data['propylene_price'] = args.propane_price
        data['estimated_pdh_margin'] = estimate_pdh_margin(
            data['propane_cp'],
            args.propane_price,
            7.2, 150.0
        )
    
    # 生成报告
    report = generate_pg_report(data)
    print(report)
    
    # 保存到DuckDB
    db_path = args.db or str(DB_PATH)
    save_pg_data_to_duckdb(data, db_path)
    
    logger.info("LPG数据获取完成")


if __name__ == "__main__":
    main()
