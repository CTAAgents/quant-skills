#!/usr/bin/env python3
"""
futures-data-search 技能测试脚本
"""

import sys
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from entity_extractor import EntityExtractor
from dominant_mapping import DominantMappingCalculator, ContractInfo
from nl2fql_engine import NL2FQLEngine, QueryType


def test_entity_extraction():
    """测试实体抽取"""
    print("=" * 60)
    print("测试实体抽取")
    print("=" * 60)

    extractor = EntityExtractor()

    test_cases = [
        ("铜今天行情", "CU", ["quote"]),
        ("铁矿石主力前20持仓", "I", ["oi_ranking"]),
        ("铜的仓单和交割信息", "CU", ["warehouse", "delivery"]),
        ("螺卷差多少", None, ["arbitrage"]),
        ("豆粕近期走势", "M", ["quote"]),
        ("CU2609价格", "CU", ["quote"]),
        ("上期所铜合约列表", "CU", ["quote"]),
        ("LPG行情", "PG", ["quote"]),
        ("纯碱仓单", "SA", ["warehouse"]),
        ("黄金期货最新价格", "AU", ["quote"]),
    ]

    for text, expected_variety, expected_metrics in test_cases:
        entity = extractor.extract(text)
        tools = extractor.select_tools(entity)

        print(f"\n输入: {text}")
        print(f"  品种: {entity.variety} (期望: {expected_variety})")
        print(f"  指标: {entity.metrics} (期望: {expected_metrics})")
        print(f"  工具: {[t['tool'] for t in tools]}")

        # 验证品种
        if expected_variety:
            assert entity.variety == expected_variety, f"品种不匹配: {entity.variety} != {expected_variety}"

        # 验证指标
        for metric in expected_metrics:
            assert metric in entity.metrics, f"缺少指标: {metric}"

    print("\n✅ 实体抽取测试通过")


def test_dominant_mapping():
    """测试主力映射算法"""
    print("\n" + "=" * 60)
    print("测试主力映射算法")
    print("=" * 60)

    calculator = DominantMappingCalculator()

    # 模拟合约数据
    contracts = [
        ContractInfo(
            code="CU2607",
            volume=50000,
            open_interest=80000,
            last_trade_date="2026-07-15",
            close_price=78200,
            delivery_month="2607"
        ),
        ContractInfo(
            code="CU2608",
            volume=100000,
            open_interest=150000,
            last_trade_date="2026-08-15",
            close_price=78450,
            delivery_month="2608"
        ),
        ContractInfo(
            code="CU2609",
            volume=120000,
            open_interest=180000,
            last_trade_date="2026-09-15",
            close_price=78780,
            delivery_month="2609"
        ),
        ContractInfo(
            code="CU2610",
            volume=80000,
            open_interest=120000,
            last_trade_date="2026-10-15",
            close_price=79010,
            delivery_month="2610"
        ),
    ]

    # 测试场景1：当前主力是 CU2608，持仓量最大是 CU2609
    result = calculator.calculate_dominant(
        variety="CU",
        contracts=contracts,
        current_main="CU2608",
        trade_date="2026-06-27"
    )

    print("\n场景1：当前主力 CU2608，持仓量最大 CU2609")
    print(f"  新主力: {result['main']}")
    print(f"  次主力: {result['next_main']}")
    print(f"  是否切换: {result['switched']}")

    # 验证：CU2609 持仓量 180000 > CU2608 持仓量 150000 × 1.1 = 165000
    # 且 CU2609 是远月（2609 > 2608），应该切换
    assert result['main'] == "CU2609", f"主力不匹配: {result['main']}"
    assert result['switched'] == True, "应该切换"

    # 测试场景2：当前主力是 CU2609，持仓量最大仍是 CU2609
    result2 = calculator.calculate_dominant(
        variety="CU",
        contracts=contracts,
        current_main="CU2609",
        trade_date="2026-06-27"
    )

    print("\n场景2：当前主力 CU2609，持仓量最大仍是 CU2609")
    print(f"  新主力: {result2['main']}")
    print(f"  是否切换: {result2['switched']}")

    # 验证：应该维持
    assert result2['main'] == "CU2609", f"主力不匹配: {result2['main']}"
    assert result2['switched'] == False, "不应该切换"

    print("\n✅ 主力映射算法测试通过")


def test_variety_resolution():
    """测试品种解析"""
    print("\n" + "=" * 60)
    print("测试品种解析")
    print("=" * 60)

    extractor = EntityExtractor()

    test_cases = [
        ("CU", "CU", "铜"),
        ("铜", "CU", "铜"),
        ("沪铜", "CU", "铜"),
        ("铁矿", "I", "铁矿石"),
        ("LPG", "PG", "液化石油气"),
        ("纯碱", "SA", "纯碱"),
        ("黄金", "AU", "黄金"),
        ("螺纹钢", "RB", "螺纹钢"),
    ]

    for input_text, expected_code, expected_name in test_cases:
        entity = extractor.extract(input_text + "行情")
        print(f"\n输入: {input_text}")
        print(f"  品种代码: {entity.variety} (期望: {expected_code})")
        print(f"  品种名称: {entity.variety_name} (期望: {expected_name})")

        if expected_code:
            assert entity.variety == expected_code, f"品种代码不匹配: {entity.variety} != {expected_code}"
            assert entity.variety_name == expected_name, f"品种名称不匹配: {entity.variety_name} != {expected_name}"

    print("\n✅ 品种解析测试通过")


# ==================== NL2FQLEngine 测试 ====================

def test_nl2fql_basic_queries():
    """F1-F6: 基本查询类型识别"""
    engine = NL2FQLEngine()
    cases = [
        ("沪铜主力最新价", QueryType.QUOTE, ["CU"]),
        ("螺纹钢2609持仓排名", QueryType.OI_RANKING, ["RB"]),
        ("纯碱仓单", QueryType.WAREHOUSE, ["SA"]),
        ("豆粕期限结构", QueryType.TERM_STRUCTURE, ["M"]),
        ("螺卷差", QueryType.SPREAD, ["RB", "HC"]),
        ("铜今天有什么公告", QueryType.NEWS, ["CU"]),
    ]
    for text, exp_type, exp_vars in cases:
        q = engine.parse(text)
        assert q.query_type == exp_type, f"{text}: type {q.query_type} != {exp_type}"
        assert set(q.varieties) == set(exp_vars), f"{text}: varieties {q.varieties} != {exp_vars}"


def test_nl2fql_entity_parsing():
    """E1-E6: 实体解析准确性"""
    engine = NL2FQLEngine()
    # E1: 铜别名
    for t in ["沪铜行情", "铜行情", "阴极铜行情"]:
        assert engine.parse(t).varieties == ["CU"], f"E1 fail: {t}"
    # E2: 螺纹别名
    for t in ["螺纹行情", "螺纹钢行情", "钢行情"]:
        assert engine.parse(t).varieties == ["RB"], f"E2 fail: {t}"
    # E3: LPG -> PG
    assert engine.parse("LPG行情").varieties == ["PG"]
    # E4: 纯碱->SA, 烧碱->SH
    assert engine.parse("纯碱行情").varieties == ["SA"]
    assert engine.parse("烧碱行情").varieties == ["SH"]
    # E5: 多晶硅 -> PS, 聚丙烯 -> PP
    assert engine.parse("多晶硅行情").varieties == ["PS"]
    assert engine.parse("聚丙烯行情").varieties == ["PP"]
    # E6: 拒绝未知复合词
    for t in ["铜锌合金行情", "XYZ行情", "不存在的品种行情"]:
        q = engine.parse(t)
        assert len(q.varieties) == 0 or len(q.parse_errors) > 0, f"E6 fail: {t}"


def test_nl2fql_boundary():
    """英文代码边界测试（修复 \b Unicode 问题）"""
    engine = NL2FQLEngine()
    # 英文代码 + 中文字符
    assert engine.parse("PG行情").varieties == ["PG"]
    assert engine.parse("SA行情").varieties == ["SA"]
    # 合约代码不应匹配为品种
    assert len(engine.parse("CU2609持仓").varieties) == 0
    # 带分隔符的多品种
    assert engine.parse("铜和锌行情").varieties == ["CU", "ZN"]


def test_nl2fql_spread_pairs():
    """多腿价差对"""
    engine = NL2FQLEngine()
    sp = engine.parse("钢厂利润")
    assert sp.query_type == QueryType.SPREAD
    assert len(sp.varieties) >= 3
    sp2 = engine.parse("石化利润")
    assert sp2.query_type == QueryType.SPREAD
    assert len(sp2.varieties) >= 3
    # 标准价差
    sp3 = engine.parse("RB-HC价差")
    assert sp3.query_type == QueryType.SPREAD
    assert {"RB", "HC"}.issubset(sp3.varieties)


def test_nl2fql_time_parsing():
    """时间范围解析"""
    engine = NL2FQLEngine()
    q = engine.parse("铜近期行情")
    assert q.relative_time == "last_5_days"
    q2 = engine.parse("铜今天行情")
    assert q2.relative_time == "today"


def test_nl2fql_yaml_loading():
    """YAML 文件别名加载"""
    engine = NL2FQLEngine()
    # YAML 提供的别名（硬编码字典未覆盖的）
    assert engine.parse("沪铝行情").varieties == ["AL"]
    assert engine.parse("沪锌行情").varieties == ["ZN"]
    # 别名总数 >= 170
    assert len(engine.variety_aliases) >= 170


def test_nl2fql_to_dict():
    """to_dict() 不应包含无效 sql 字段"""
    engine = NL2FQLEngine()
    d = engine.parse("沪铜").to_dict()
    assert "sql" not in d


def test_nl2fql_performance():
    """解析性能 < 200ms"""
    import time
    engine = NL2FQLEngine()
    inputs = ["铜主力合约最新价格", "螺纹钢2609持仓排名", "纯碱仓单", "豆粕期限结构", "螺卷差"]
    for t in inputs:
        start = time.time()
        engine.parse(t)
        elapsed = (time.time() - start) * 1000
        assert elapsed < 200, f"慢查询: {t} = {elapsed:.1f}ms"


def main():
    """运行所有测试"""
    print("🚀 开始测试 futures-data-search 技能\n")

    try:
        test_variety_resolution()
        test_entity_extraction()
        test_dominant_mapping()

        # NL2FQLEngine 测试
        test_nl2fql_basic_queries()
        test_nl2fql_entity_parsing()
        test_nl2fql_boundary()
        test_nl2fql_spread_pairs()
        test_nl2fql_time_parsing()
        test_nl2fql_yaml_loading()
        test_nl2fql_to_dict()
        test_nl2fql_performance()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
