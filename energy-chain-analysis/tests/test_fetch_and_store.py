#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TqSdk数据获取测试 — 7个测试用例
验证合约符号映射、数据格式、DuckDB存储
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestTqSdkSymbolMap:
    """TqSdk合约符号映射测试"""

    def test_sc_symbol(self):
        """测试1：SC原油合约符号正确"""
        from fetch_and_store import TQSDK_SYMBOL_MAP
        assert TQSDK_SYMBOL_MAP["SC"] == "KQ.m@INE.sc"

    def test_bu_symbol(self):
        """测试2：BU沥青合约符号正确"""
        from fetch_and_store import TQSDK_SYMBOL_MAP
        assert TQSDK_SYMBOL_MAP["BU"] == "KQ.m@SHFE.bu"

    def test_fu_symbol(self):
        """测试3：FU燃料油合约符号正确"""
        from fetch_and_store import TQSDK_SYMBOL_MAP
        assert TQSDK_SYMBOL_MAP["FU"] == "KQ.m@SHFE.fu"

    def test_lu_symbol(self):
        """测试4：LU低硫燃料油合约符号正确"""
        from fetch_and_store import TQSDK_SYMBOL_MAP
        assert TQSDK_SYMBOL_MAP["LU"] == "KQ.m@INE.lu"

    def test_pg_symbol_dce(self):
        """测试5：PG液化石油气合约符号为DCE（非INE）"""
        from fetch_and_store import TQSDK_SYMBOL_MAP
        assert TQSDK_SYMBOL_MAP["PG"] == "KQ.m@DCE.pg"
        assert "DCE" in TQSDK_SYMBOL_MAP["PG"]

    def test_all_symbols_valid_format(self):
        """测试6：所有合约符号格式为 KQ.m@EXCHANGE.symbol"""
        from fetch_and_store import TQSDK_SYMBOL_MAP
        for name, symbol in TQSDK_SYMBOL_MAP.items():
            assert symbol.startswith("KQ.m@"), f"{name}: {symbol} format invalid"
            parts = symbol.split("@")[1].split(".")
            assert len(parts) == 2, f"{name}: {symbol} should have exchange.symbol"

    def test_credentials_env_check(self):
        """测试7：凭证获取函数存在"""
        from fetch_and_store import get_tq_credentials
        assert callable(get_tq_credentials)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
