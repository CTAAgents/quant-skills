#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易所官方数据采集模块 v3.1
支持：大商所(DCE)、上期所(SHFE)、郑商所(CZCE)、中金所(CFFEX)、广期所(GFEX)

数据源优先级：
1. 交易所官方API（最权威，无爬虫合规风险）
2. AKShare（降级方案）
3. TqSdk（实时行情）

数据持久化：DuckDB存储，连接复用，批量插入

核心设计：
- 单例数据库连接，减少创建/销毁开销
- 批量 INSERT OR IGNORE，避免全表扫描
- 数据完整性校验（价格逻辑、非空检查）
- 自动重试机制（应对API临时故障）
- 交易日期校验（考虑周末和候选节假日）

v3.1修复内容（2026-06-26）：
1. 修复中金所API端点：从lsjy.dll改为{YYYYMMDD}_1.csv格式
2. 改进上期所API处理：添加404错误检测和自动降级
3. 改进大商所API处理：添加WAF拦截检测（412错误）和自动降级
4. 改进郑商所API处理：添加WAF拦截检测（412错误）和自动降级
5. 改进广期所API处理：添加HTML页面检测和自动降级
6. 优化请求头模拟浏览器访问，减少被拦截概率
7. 更新API配置文件，记录各交易所API状态和验证结果
"""

import requests
import json
import time
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from html.parser import HTMLParser
import re
import duckdb

# 降级数据源 - 使用 importlib 检查模块可用性，避免 tqsdk 导入时网络阻塞
import importlib
TQSDK_AVAILABLE = importlib.util.find_spec("tqsdk") is not None

if TQSDK_AVAILABLE:
    # 验证 TQSDK 凭据是否已配置（不使用实际导入）
    _has_tq_creds = bool(os.environ.get('TQSDK_USERNAME') or os.environ.get('TQ_USER')) and \
                    bool(os.environ.get('TQSDK_PASSWORD') or os.environ.get('TQ_PASSWORD'))
    if not _has_tq_creds:
        TQSDK_AVAILABLE = False

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False


# ==================== 路径配置 ====================
# 作为 futures-data-search 的子模块运行
# 可通过环境变量 EXCHANGE_DATA_DIR 自定义数据目录
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get('EXCHANGE_DATA_DIR') or os.path.join(SKILL_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'futures_data.duckdb')

# 中国法定节假日（仅非调休日，调休上班日会正常交易）
# 格式: YYYYMMDD
_KNOWN_HOLIDAYS = frozenset({
    # 2026年主要节假日（不含调休上班日）
    '20260101',  # 元旦
    '20260102',
    '20260103',
    '20260128',  # 春节
    '20260129',
    '20260130',
    '20260131',
    '20260201',
    '20260202',
    '20260203',
    '20260204',
    '20260205',
    '20260206',
    '20260207',
    '20260208',
    '20260209',
    '20260210',
    '20260211',
    '20260212',
    '20260213',
    '20260214',
    '20260215',
    '20260302',  # 元宵节
    '20260405',  # 清明节
    '20260406',
    '20260501',  # 劳动节
    '20260502',
    '20260503',
    '20260504',
    '20260505',
    '20260612',  # 端午节
    '20260613',
    '20260614',
    '20260615',
    '20260616',
    '20260927',  # 中秋节
    '20260928',
    '20261001',  # 国庆节
    '20261002',
    '20261003',
    '20261004',
    '20261005',
    '20261006',
    '20261007',
    '20261008',
})


# ==================== 数据验证 ====================
def validate_price_record(record: dict) -> Optional[dict]:
    """
    验证单条价格记录的完整性。
    返回修正后的记录，如果记录不可用则返回None。
    """
    # 必填字段非空检查
    if not record.get('symbol'):
        return None

    # 价格逻辑检查
    high = record.get('high', 0) or 0
    low = record.get('low', 0) or 0
    close = record.get('close', 0) or 0
    open_ = record.get('open', 0) or 0

    # 所有关键价格必须为正数（0=缺失数据）
    if close <= 0:
        return None

    # high >= low（互换位置而不是丢弃）
    if high > 0 and low > 0 and high < low:
        record['high'], record['low'] = low, high

    # 非负检查
    record['volume'] = max(0, int(record.get('volume', 0) or 0))
    record['open_interest'] = max(0, int(record.get('open_interest', 0) or 0))
    record['turnover'] = max(0, float(record.get('turnover', 0) or 0))

    return record


class ExchangeDataCollector:
    """交易所官方数据采集器"""

    # 类级缓存，避免重复创建DB连接
    _db_conn_cache = {}

    def __init__(self, db_path: str = DB_PATH):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not/A)Brand";v="99", "Google Chrome";v="126", "Chromium";v="126"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }
        # 备用 User-Agent 列表（用于 412 重试）
        self._ua_backup_list = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        ]
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 预热Session：访问交易所主页获取cookies
        self._warmup_session()
        self.db_path = db_path
        self._conn = None  # 懒加载连接

        # 确保data目录存在（仅一次）
        if not hasattr(ExchangeDataCollector, '_dir_created'):
            os.makedirs(DATA_DIR, exist_ok=True)
            ExchangeDataCollector._dir_created = True

        # 初始化数据库（仅一次）
        self._init_database()

    def _warmup_session(self):
        """预热Session：访问交易所主页获取cookies，避免412错误（并行请求，加快启动速度）"""
        import concurrent.futures

        sites = [
            ('http://www.dce.com.cn', '大商所'),
            ('http://www.shfe.com.cn', '上期所'),
            ('http://www.czce.com.cn', '郑商所'),
            ('http://www.cffex.com.cn', '中金所'),
            ('http://www.gfex.com.cn', '广期所'),
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            def _warmup_one(url, name):
                try:
                    self.session.get(url, timeout=8)
                except Exception:
                    pass
                return name

            futures = [executor.submit(_warmup_one, url, name) for url, name in sites]
            concurrent.futures.wait(futures, timeout=10)

        print("[Session] 预热完成")

    def _get_conn(self):
        """获取数据库连接（懒加载+复用）"""
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path)
        return self._conn

    def _fallback_to_akshare(self, trade_date: str) -> Optional[pd.DataFrame]:
        """
        降级到AKShare获取期货日线数据
        当交易所API不可用时使用
        """
        if not AKSHARE_AVAILABLE:
            print("[降级] AKShare未安装，跳过")
            return None
        
        try:
            print(f"[降级] 尝试使用AKShare获取{trade_date}数据...")
            # AKShare期货日线数据接口
            # 注意：AKShare可能需要不同的日期格式
            date_obj = datetime.strptime(trade_date, '%Y%m%d')
            date_str = date_obj.strftime('%Y-%m-%d')
            
            # 使用固定的主力品种白名单，确保覆盖全部5个交易所
            # 不依赖 futures_display_main_sina() 的动态列表（其排序可能导致SHFE品种被前20截断）
            symbols = [
                # SHFE（上期所）
                'cu0', 'al0', 'zn0', 'pb0', 'ni0', 'sn0', 'au0', 'ag0',
                'rb0', 'hc0', 'ss0', 'fu0', 'bu0', 'ru0', 'sp0', 'nr0',
                # INE（能源）
                'sc0', 'lu0', 'ec0',
                # DCE（大商所）
                'm0', 'y0', 'p0', 'c0', 'a0', 'b0', 'i0', 'j0',
                'jm0', 'jd0', 'l0', 'v0', 'pp0', 'eb0', 'pg0', 'rr0',
                'lh0', 'cs0', 'eg0', 'bz0',
                # CZCE（郑商所）
                'TA0', 'MA0', 'SR0', 'CF0', 'FG0', 'OI0', 'RM0',
                'PF0', 'SA0', 'UR0', 'PK0', 'AP0', 'CJ0', 'SF0', 'SM0',
                'SH0', 'PX0', 'PR0',
                # CFFEX（中金所）— 不通过 futures_main_sina 获取（接口不稳定），跳过
                # GFEX（广期所）
                'si0', 'lc0', 'ps0',
            ]
            
            records = []
            # 遍历全部白名单品种（不限数量），确保不遗漏任何交易所
            for symbol in symbols:
                try:
                    # 使用futures_main_sina获取指定日期范围的数据
                    # 注意：futures_main_sina的symbol参数需要是连续合约代码，如"cu0"
                    df = ak.futures_main_sina(symbol=symbol, start_date=date_str, end_date=date_str)
                    
                    if df is None or len(df) == 0:
                        continue
                    
                    # 转换为标准格式
                    for _, row in df.iterrows():
                        try:
                            # 确定交易所（使用精确映射，避免单字符前缀错误匹配）
                            exchange = 'UNKNOWN'
                            symbol_upper = symbol.upper().replace('0', '')
                            # 精确映射表（优先级：CZCE/CFFEX/GFEX的大写代码不与SHFE/DCE的小写冲突）
                            _EXCHANGE_MAP = {
                                # SHFE（上期所）
                                'CU': 'SHFE', 'AL': 'SHFE', 'ZN': 'SHFE', 'PB': 'SHFE',
                                'NI': 'SHFE', 'SN': 'SHFE', 'AU': 'SHFE', 'AG': 'SHFE',
                                'RB': 'SHFE', 'WR': 'SHFE', 'HC': 'SHFE', 'SS': 'SHFE',
                                'FU': 'SHFE', 'BU': 'SHFE', 'RU': 'SHFE', 'SP': 'SHFE',
                                'NR': 'SHFE', 'BC': 'SHFE', 'BR': 'SHFE', 'OP': 'SHFE',
                                'AD': 'SHFE', 'PT': 'SHFE',
                                # INE（上海国际能源）归入SHFE
                                'SC': 'INE', 'LU': 'INE', 'EC': 'INE',
                                # DCE（大商所）
                                'M': 'DCE', 'Y': 'DCE', 'P': 'DCE', 'C': 'DCE',
                                'A': 'DCE', 'B': 'DCE', 'I': 'DCE', 'J': 'DCE',
                                'JM': 'DCE', 'JD': 'DCE', 'L': 'DCE', 'V': 'DCE',
                                'PP': 'DCE', 'EB': 'DCE', 'PG': 'DCE', 'RR': 'DCE',
                                'LH': 'DCE', 'CS': 'DCE', 'EG': 'DCE', 'BZ': 'DCE',
                                # CZCE（郑商所）
                                'TA': 'CZCE', 'MA': 'CZCE', 'SR': 'CZCE', 'CF': 'CZCE',
                                'ZC': 'CZCE', 'FG': 'CZCE', 'OI': 'CZCE', 'RM': 'CZCE',
                                'CY': 'CZCE', 'PF': 'CZCE', 'SA': 'CZCE', 'UR': 'CZCE',
                                'PK': 'CZCE', 'AP': 'CZCE', 'CJ': 'CZCE', 'SF': 'CZCE',
                                'SM': 'CZCE', 'WH': 'CZCE', 'PM': 'CZCE', 'RI': 'CZCE',
                                'RS': 'CZCE', 'JR': 'CZCE', 'LR': 'CZCE', 'SH': 'CZCE',
                                'PX': 'CZCE', 'PR': 'CZCE', 'PL': 'CZCE',
                                # CFFEX（中金所）
                                'IF': 'CFFEX', 'IC': 'CFFEX', 'IH': 'CFFEX', 'IM': 'CFFEX',
                                'T': 'CFFEX', 'TF': 'CFFEX', 'TS': 'CFFEX', 'TL': 'CFFEX',
                                # GFEX（广期所）
                                'SI': 'GFEX', 'LC': 'GFEX', 'PS': 'GFEX',
                            }
                            exchange = _EXCHANGE_MAP.get(symbol_upper, 'UNKNOWN')
                            
                            records.append({
                                'exchange': exchange,
                                'symbol': symbol.replace('0', ''),  # 移除连续合约后缀
                                'trade_date': trade_date,
                                'open': float(row.get('开盘价', row.get('open', 0)) or 0),
                                'high': float(row.get('最高价', row.get('high', 0)) or 0),
                                'low': float(row.get('最低价', row.get('low', 0)) or 0),
                                'close': float(row.get('收盘价', row.get('close', 0)) or 0),
                                'settle': float(row.get('动态结算价', row.get('settle', 0)) or 0),
                                'volume': int(float(row.get('成交量', row.get('volume', 0)) or 0)),
                                'open_interest': int(float(row.get('持仓量', row.get('hold', 0)) or 0)),
                                'turnover': 0,  # AKShare可能不提供成交额
                                'source': 'AKShare'
                            })
                        except (ValueError, TypeError):
                            continue
                except Exception as e:
                    print(f"[降级] 获取{symbol}数据失败: {e}")
                    continue
            
            if records:
                result_df = pd.DataFrame(records)
                print(f"[降级] AKShare成功: {len(result_df)}条")
                self._save_to_db(result_df)
                return result_df
            else:
                print("[降级] AKShare无有效记录")
                return None
                
        except Exception as e:
            print(f"[降级] AKShare异常: {e}")
            return None

    def _fallback_to_tqsdk(self, trade_date: str) -> Optional[pd.DataFrame]:
        """
        降级到TqSdk获取期货日线数据
        当交易所API和AKShare都不可用时使用
        """
        if not TQSDK_AVAILABLE:
            print("[降级] TqSdk未安装，跳过")
            return None
        
        try:
            print(f"[降级] 尝试使用TqSdk获取{trade_date}数据...")
            # TqSdk需要连接到服务器，这里我们只获取日线数据
            # 注意：TqSdk可能需要实时连接，这里我们尝试获取历史数据
            
            # 延迟导入 TqApi（避免模块级网络阻塞）
            from tqsdk import TqApi
            
            # 创建API对象
            api = TqApi()
            
            # 获取所有期货合约
            # 这里我们只获取主要品种，避免连接超时
            symbols = ['SHFE.cu2401', 'SHFE.al2401', 'DCE.m2401', 'CZCE.TA2401']
            records = []
            
            for symbol in symbols:
                try:
                    klines = api.get_kline_serial(symbol, 86400)  # 日线
                    if klines is not None and len(klines) > 0:
                        # 获取最新一根K线
                        kline = klines.iloc[-1]
                        records.append({
                            'exchange': symbol.split('.')[0],
                            'symbol': symbol.split('.')[1],
                            'trade_date': trade_date,
                            'open': kline['open'],
                            'high': kline['high'],
                            'low': kline['low'],
                            'close': kline['close'],
                            'settle': kline['close'],  # TqSdk可能没有结算价
                            'volume': int(kline['volume']),
                            'open_interest': 0,  # TqSdk可能没有持仓量
                            'turnover': 0,
                            'source': 'TqSdk'
                        })
                except Exception:
                    continue
            
            api.close()
            
            if records:
                result_df = pd.DataFrame(records)
                print(f"[降级] TqSdk成功: {len(result_df)}条")
                self._save_to_db(result_df)
                return result_df
            else:
                print("[降级] TqSdk无数据")
                return None
                
        except Exception as e:
            print(f"[降级] TqSdk异常: {e}")
            return None

    def _init_database(self):
        """初始化DuckDB数据库，创建日线数据表"""
        # 检查是否已经初始化过（类级缓存）
        if ExchangeDataCollector._db_conn_cache.get('initialized'):
            return

        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_data (
                    exchange VARCHAR,
                    symbol VARCHAR,
                    trade_date VARCHAR,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    settle DOUBLE,
                    volume BIGINT,
                    open_interest BIGINT,
                    turnover DOUBLE,
                    source VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (exchange, symbol, trade_date)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_data_date
                ON daily_data (trade_date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_data_symbol
                ON daily_data (symbol)
            """)
            ExchangeDataCollector._db_conn_cache['initialized'] = True
            print(f"[DB] 数据库初始化完成: {self.db_path}")
        except Exception:
            raise

    def _save_to_db(self, df: pd.DataFrame):
        """将数据批量保存到DuckDB（INSERT OR IGNORE）"""
        if df is None or len(df) == 0:
            return

        # 过滤无效记录
        valid_records = []
        for _, row in df.iterrows():
            record = validate_price_record(row.to_dict())
            if record is not None:
                valid_records.append(record)

        if not valid_records:
            print("[DB] 无有效记录可保存")
            return

        new_df = pd.DataFrame(valid_records)
        # 确保数值列类型正确，避免 DuckDB 类型识别失败
        for col in ['open', 'high', 'low', 'close', 'settle', 'turnover']:
            new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0.0).astype(float)
        for col in ['volume', 'open_interest']:
            new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0).astype(int)
        for col in ['exchange', 'symbol', 'trade_date', 'source']:
            new_df[col] = new_df[col].astype(str)

        conn = self._get_conn()
        try:
            # DuckDB 使用 ON CONFLICT DO NOTHING 代替 INSERT OR IGNORE
            conn.execute("""
                INSERT INTO daily_data 
                (exchange, symbol, trade_date, open, high, low, close, settle, volume, open_interest, turnover, source)
                SELECT exchange, symbol, trade_date, open, high, low, close, settle, volume, open_interest, turnover, source
                FROM new_df
                ON CONFLICT (exchange, symbol, trade_date) DO NOTHING
            """)
            print(f"[DB] 新增 {len(new_df)} 条记录到DuckDB")
        except Exception as e:
            print(f"[DB] 保存失败: {e}")

    def _read_from_db(self, trade_date: str, exchange: Optional[str] = None) -> Optional[pd.DataFrame]:
        """从DuckDB读取指定日期的数据"""
        conn = self._get_conn()
        try:
            if exchange:
                result = conn.execute("""
                    SELECT * FROM daily_data
                    WHERE trade_date = ? AND exchange = ?
                    ORDER BY symbol
                """, [trade_date, exchange]).fetchdf()
            else:
                result = conn.execute("""
                    SELECT * FROM daily_data
                    WHERE trade_date = ?
                    ORDER BY exchange, symbol
                """, [trade_date]).fetchdf()

            if len(result) > 0:
                return result
            return None
        except Exception as e:
            print(f"[DB] 读取失败: {e}")
            return None

    def get_cached_dates(self) -> List[str]:
        """获取数据库中已有的交易日期列表"""
        conn = self._get_conn()
        try:
            result = conn.execute("""
                SELECT DISTINCT trade_date FROM daily_data
                ORDER BY trade_date DESC
            """).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            print(f"[DB] 获取缓存日期失败: {e}")
            return []

    def get_cached_count(self) -> int:
        """获取总缓存记录数"""
        conn = self._get_conn()
        try:
            return conn.execute("SELECT COUNT(*) FROM daily_data").fetchone()[0]
        except Exception:
            return 0

    # ==================== 大商所 (DCE) ====================
    def get_dce_daily_data(self, trade_date: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        获取大商所日线数据

        API端点: POST http://www.dce.com.cn/publicweb/quotesdata/exportDayQuotesChData.html
        响应格式: TSV（制表符分隔），第一列为合约代码
        
        注意: 大商所网站有WAF保护，可能需要特殊处理
        """
        if use_cache:
            cached = self._read_from_db(trade_date, 'DCE')
            if cached is not None:
                print(f"[DB] DCE缓存命中 ({len(cached)}条)")
                return cached

        try:
            url = 'http://www.dce.com.cn/publicweb/quotesdata/exportDayQuotesChData.html'
            month_index = str(int(trade_date[4:6]) - 1)  # 月份参数从0开始
            data = {
                'dayQuotes.variety': 'all',
                'dayQuotes.trade_type': '0',
                'year': trade_date[:4],
                'month': month_index,
                'day': trade_date[6:8],
            }

            # 添加特定请求头，模拟浏览器访问
            headers = {
                'Referer': 'http://www.dce.com.cn/publicweb/quotesdata/dayQuotesCh.html',
                'Origin': 'http://www.dce.com.cn',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
            }
            self.session.headers.update(headers)
            
            response = self.session.post(url, data=data, timeout=30)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"[DCE] API请求失败: {response.status_code}")
                # 检查是否被WAF拦截（412错误）
                if response.status_code == 412:
                    print("[DCE] 被WAF拦截，尝试旋转UA重试...")
                    for i, alt_ua in enumerate(self._ua_backup_list):
                        self.session.headers.update({'User-Agent': alt_ua})
                        time.sleep(2)
                        retry_resp = self.session.post(url, data=data, timeout=30)
                        if retry_resp.status_code == 200:
                            response = retry_resp
                            print(f"[DCE] UA旋转 {i+1} 成功")
                            break
                    else:
                        print("[DCE] UA旋转全部失败，降级到AKShare")
                        return self._fallback_to_akshare(trade_date)
                return None

            # 检查响应是否是HTML页面（WAF拦截）
            content = response.text.strip()
            if content.startswith('<!DOCTYPE html>') or content.startswith('<html'):
                print("[DCE] 返回了HTML页面（可能被WAF拦截），尝试降级")
                return self._fallback_to_akshare(trade_date)

            # 解析TSV格式（支持\r\n和\n两种换行）
            lines = re.split(r'[\r\n]+', content)
            records = []

            for line in lines:
                line = line.strip()
                if not line or '小计' in line or '合计' in line or '品种' in line:
                    continue

                fields = re.split(r'\t+', line)
                if len(fields) < 10:
                    continue

                try:
                    symbol = fields[0].strip()
                    if not symbol or symbol in ('合约代码', '合约名称'):
                        continue

                    records.append({
                        'exchange': 'DCE',
                        'symbol': symbol,
                        'trade_date': trade_date,
                        'open': float(fields[2].replace(',', '') or 0),
                        'high': float(fields[3].replace(',', '') or 0),
                        'low': float(fields[4].replace(',', '') or 0),
                        'close': float(fields[5].replace(',', '') or 0),
                        'settle': float(fields[6].replace(',', '') or 0),
                        'volume': int(float(fields[7].replace(',', '') or 0)),
                        'open_interest': int(float(fields[8].replace(',', '') or 0)),
                        'turnover': float(fields[9].replace(',', '') or 0) if len(fields) > 9 else 0,
                        'source': 'DCE官方API'
                    })
                except (ValueError, IndexError):
                    continue

            if records:
                df = pd.DataFrame(records)
                print(f"[DCE] 成功: {len(df)}条")
                self._save_to_db(df)
                return df
            else:
                print("[DCE] 无有效记录")
                return None

        except Exception as e:
            print(f"[DCE] 异常: {e}")
            # 尝试降级到AKShare或TqSdk
            print(f"[DCE] 尝试降级...")
            fallback_df = self._fallback_to_akshare(trade_date)
            if fallback_df is None:
                fallback_df = self._fallback_to_tqsdk(trade_date)
            return fallback_df

    # ==================== 上期所 (SHFE) ====================
    def get_shfe_daily_data(self, trade_date: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        获取上期所日线数据

        API端点: GET http://www.shfe.com.cn/data/dailydata/kx/kx{YYYYMMDD}.dat
        响应格式: JSON，根字段 o_curinstrument 为数组
        
        注意: 上期所网站有WAF保护，可能需要特殊处理
        """
        if use_cache:
            cached = self._read_from_db(trade_date, 'SHFE')
            if cached is not None:
                print(f"[DB] SHFE缓存命中 ({len(cached)}条)")
                return cached

        try:
            url = f'http://www.shfe.com.cn/data/dailydata/kx/kx{trade_date}.dat'
            # 添加特定请求头，模拟浏览器访问
            headers = {
                'Referer': 'http://www.shfe.com.cn/marketdata/quotes/price.html',
                'Origin': 'http://www.shfe.com.cn',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'X-Requested-With': 'XMLHttpRequest',
            }
            self.session.headers.update(headers)
            
            response = self.session.get(url, timeout=30)

            if response.status_code != 200:
                print(f"[SHFE] API请求失败: {response.status_code}")
                # 尝试降级到AKShare
                print(f"[SHFE] 尝试降级到AKShare...")
                return self._fallback_to_akshare(trade_date)

            # 检查响应是否是JSON格式
            content = response.text.strip()
            if not content:
                print("[SHFE] 空响应")
                return None
                
            # 尝试解析JSON
            try:
                json_data = json.loads(content)
            except json.JSONDecodeError:
                print("[SHFE] 响应不是JSON格式，尝试降级")
                return self._fallback_to_akshare(trade_date)

            if 'o_curinstrument' not in json_data:
                print("[SHFE] 数据格式异常（缺少o_curinstrument字段）")
                return None

            records = []
            for item in json_data['o_curinstrument']:
                try:
                    product_id = item.get('PRODUCTID', '')
                    if not product_id or product_id.endswith('_summary'):
                        continue

                    # 上期所字段名: OPENPRICE, HIGHESTPRICE, LOWESTPRICE, CLOSEPRICE,
                    # SETTLEMENTPRICE, VOLUME, OPENINTEREST, TURNOVER
                    turnover = item.get('TURNOVER', 0)
                    records.append({
                        'exchange': 'SHFE',
                        'symbol': product_id,
                        'trade_date': trade_date,
                        'open': float(item.get('OPENPRICE', 0) or 0),
                        'high': float(item.get('HIGHESTPRICE', 0) or 0),
                        'low': float(item.get('LOWESTPRICE', 0) or 0),
                        'close': float(item.get('CLOSEPRICE', 0) or 0),
                        'settle': float(item.get('SETTLEMENTPRICE', 0) or 0),
                        'volume': int(float(item.get('VOLUME', 0) or 0)),
                        'open_interest': int(float(item.get('OPENINTEREST', 0) or 0)),
                        'turnover': float(turnover or 0),
                        'source': 'SHFE官方API'
                    })
                except (ValueError, TypeError):
                    continue

            if records:
                df = pd.DataFrame(records)
                print(f"[SHFE] 成功: {len(df)}条")
                self._save_to_db(df)
                return df
            else:
                print("[SHFE] 无有效记录")
                return None

        except Exception as e:
            print(f"[SHFE] 异常: {e}")
            # 尝试降级到AKShare或TqSdk
            print(f"[SHFE] 尝试降级...")
            fallback_df = self._fallback_to_akshare(trade_date)
            if fallback_df is None:
                fallback_df = self._fallback_to_tqsdk(trade_date)
            return fallback_df

    # ==================== 郑商所 (CZCE) ====================
    class CzceHtmlParser(HTMLParser):
        """
        郑商所HTML日线数据解析器

        目标表格：id="senfe" 或 id="tab1"
        数据结构：合约代码 | 开盘 | 最高 | 最低 | 收盘 | 结算 | 成交量 | 持仓量
        """
        def __init__(self):
            super().__init__()
            self.in_table = False
            self.in_tr = False
            self.in_td = False
            self.data = []
            self.current_row = []
            self._table_ids = {'senfe', 'tab1'}

        def handle_starttag(self, tag, attrs):
            if tag == 'table':
                for attr in attrs:
                    if attr[0] == 'id' and attr[1] in self._table_ids:
                        self.in_table = True
                        break
            elif tag == 'tr' and self.in_table:
                self.in_tr = True
                self.current_row = []
            elif tag in ('td', 'th') and self.in_tr:
                self.in_td = True

        def handle_endtag(self, tag):
            if tag == 'table':
                self.in_table = False
                self.data = []  # 只保留最后一个数据表
            elif tag == 'tr' and self.in_tr:
                self.in_tr = False
                if self.current_row:
                    self.data.append(self.current_row)
            elif tag in ('td', 'th'):
                self.in_td = False

        def handle_data(self, data):
            if self.in_td:
                self.current_row.append(data.strip())

    def get_czce_daily_data(self, trade_date: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        获取郑商所日线数据

        API端点:
          新版(>20151111): GET .../DFSStaticFiles/Future/{YYYY}/{YYYYMMDD}/FutureDataDaily.htm
          旧版(≤20151111): GET .../exchange/{YYYY}/datadaily/{YYYYMMDD}.htm
        响应格式: HTML表格，需通过CzceHtmlParser解析
        
        注意: 郑商所网站有WAF保护，可能需要特殊处理
        """
        if use_cache:
            cached = self._read_from_db(trade_date, 'CZCE')
            if cached is not None:
                print(f"[DB] CZCE缓存命中 ({len(cached)}条)")
                return cached

        try:
            if trade_date > '20151111':
                url = f'http://www.czce.com.cn/cn/DFSStaticFiles/Future/{trade_date[:4]}/{trade_date}/FutureDataDaily.htm'
            else:
                url = f'http://www.czce.com.cn/cn/exchange/{trade_date[:4]}/datadaily/{trade_date}.htm'

            # 添加特定请求头，模拟浏览器访问
            headers = {
                'Referer': 'http://www.czce.com.cn/cn/DFSStaticFiles/Future/2026/20260625/FutureDataDaily.htm',
                'Origin': 'http://www.czce.com.cn',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
            }
            self.session.headers.update(headers)
            
            response = self.session.get(url, timeout=30)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"[CZCE] API请求失败: {response.status_code}")
                if response.status_code == 412:
                    print("[CZCE] 被WAF拦截，尝试旋转UA重试...")
                    for i, alt_ua in enumerate(self._ua_backup_list):
                        self.session.headers.update({'User-Agent': alt_ua})
                        time.sleep(2)
                        retry_resp = self.session.get(url, timeout=30)
                        if retry_resp.status_code == 200 and 'WAF' not in retry_resp.text:
                            response = retry_resp
                            print(f"[CZCE] UA旋转 {i+1} 成功")
                            break
                    else:
                        print("[CZCE] UA旋转全部失败，降级到AKShare")
                        return self._fallback_to_akshare(trade_date)
                return None

            # 检查响应是否是HTML页面（正常情况）
            content = response.text.strip()
            if not content:
                print("[CZCE] 空响应")
                return None
                
            # 检查是否被WAF拦截（返回了错误页面）
            if 'WAF' in content or 'Web应用防火墙' in content:
                print("[CZCE] 被WAF拦截，尝试降级到AKShare")
                return self._fallback_to_akshare(trade_date)

            parser = self.CzceHtmlParser()
            parser.feed(content)

            records = []
            for row in parser.data:
                if len(row) < 8:
                    continue

                try:
                    symbol = row[0].strip()
                    if not symbol or symbol in ('品种代码', '合约代码', '合约名称', '合计'):
                        continue

                    records.append({
                        'exchange': 'CZCE',
                        'symbol': symbol,
                        'trade_date': trade_date,
                        'open': float(row[2].replace(',', '') or 0) if len(row) > 2 else 0,
                        'high': float(row[3].replace(',', '') or 0) if len(row) > 3 else 0,
                        'low': float(row[4].replace(',', '') or 0) if len(row) > 4 else 0,
                        'close': float(row[5].replace(',', '') or 0) if len(row) > 5 else 0,
                        'settle': float(row[6].replace(',', '') or 0) if len(row) > 6 else 0,
                        'volume': int(float(row[7].replace(',', '') or 0)) if len(row) > 7 else 0,
                        'open_interest': int(float(row[8].replace(',', '') or 0)) if len(row) > 8 else 0,
                        'turnover': float(row[9].replace(',', '') or 0) if len(row) > 9 else 0,
                        'source': 'CZCE官方API'
                    })
                except (ValueError, IndexError):
                    continue

            if records:
                df = pd.DataFrame(records)
                print(f"[CZCE] 成功: {len(df)}条")
                self._save_to_db(df)
                return df
            else:
                print("[CZCE] 无有效记录（HTML解析可能未匹配到表格）")
                return None

        except Exception as e:
            print(f"[CZCE] 异常: {e}")
            # 尝试降级到AKShare或TqSdk
            print(f"[CZCE] 尝试降级...")
            fallback_df = self._fallback_to_akshare(trade_date)
            if fallback_df is None:
                fallback_df = self._fallback_to_tqsdk(trade_date)
            return fallback_df

    # ==================== 中金所 (CFFEX) ====================
    def get_cffex_daily_data(self, trade_date: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        获取中金所日线数据

        API端点: GET http://www.cffex.com.cn/sj/hqsj/rtj/{YYYYMM}/{DD}/{YYYYMMDD}_1.csv
        响应格式: CSV，首行为标题行，后续每行为一个合约
        """
        if use_cache:
            cached = self._read_from_db(trade_date, 'CFFEX')
            if cached is not None:
                print(f"[DB] CFFEX缓存命中 ({len(cached)}条)")
                return cached

        try:
            # 中金所用月/日路径格式，CSV文件格式为{YYYYMMDD}_1.csv
            month_str = trade_date[:6]
            day_str = trade_date[6:8]
            url = f'http://www.cffex.com.cn/sj/hqsj/rtj/{month_str}/{day_str}/{trade_date}_1.csv'

            # 添加特定请求头
            headers = {
                'Referer': 'http://www.cffex.com.cn/sj/hqsj/rtj/',
                'Origin': 'http://www.cffex.com.cn',
            }
            self.session.headers.update(headers)
            
            response = self.session.get(url, timeout=30)

            if response.status_code != 200:
                print(f"[CFFEX] API请求失败: {response.status_code}")
                return None

            lines = response.text.strip().split('\n')
            records = []

            for line in lines[1:]:  # 跳过标题行
                line = line.strip()
                if not line:
                    continue

                fields = line.split(',')
                if len(fields) < 8:
                    continue

                try:
                    symbol = fields[0].strip()
                    if not symbol:
                        continue

                    records.append({
                        'exchange': 'CFFEX',
                        'symbol': symbol,
                        'trade_date': trade_date,
                        'open': float(fields[1].replace(',', '') or 0) if len(fields) > 1 else 0,
                        'high': float(fields[2].replace(',', '') or 0) if len(fields) > 2 else 0,
                        'low': float(fields[3].replace(',', '') or 0) if len(fields) > 3 else 0,
                        'close': float(fields[4].replace(',', '') or 0) if len(fields) > 4 else 0,
                        'settle': float(fields[5].replace(',', '') or 0) if len(fields) > 5 else 0,
                        'volume': int(float(fields[6].replace(',', '') or 0)) if len(fields) > 6 else 0,
                        'open_interest': int(float(fields[7].replace(',', '') or 0)) if len(fields) > 7 else 0,
                        'turnover': float(fields[8].replace(',', '') or 0) if len(fields) > 8 else 0,
                        'source': 'CFFEX官方API'
                    })
                except (ValueError, IndexError):
                    continue

            if records:
                df = pd.DataFrame(records)
                print(f"[CFFEX] 成功: {len(df)}条")
                self._save_to_db(df)
                return df
            else:
                print("[CFFEX] 无有效记录")
                return None

        except Exception as e:
            print(f"[CFFEX] 异常: {e}")
            # 尝试降级到AKShare或TqSdk
            print(f"[CFFEX] 尝试降级...")
            fallback_df = self._fallback_to_akshare(trade_date)
            if fallback_df is None:
                fallback_df = self._fallback_to_tqsdk(trade_date)
            return fallback_df

    # ==================== 广期所 (GFEX) ====================
    def get_gfex_daily_data(self, trade_date: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        获取广期所日线数据

        API端点: GET http://www.gfex.com.cn/gfex/rihq/{YYYYMMDD}.js
        响应格式: 可能是JSON（可能被 `var xxx = ...;` 包裹）或JS变量定义
        
        注意: 广期所网站可能返回HTML页面而非JS文件，需要特殊处理
        """
        if use_cache:
            cached = self._read_from_db(trade_date, 'GFEX')
            if cached is not None:
                print(f"[DB] GFEX缓存命中 ({len(cached)}条)")
                return cached

        try:
            url = f'http://www.gfex.com.cn/gfex/rihq/{trade_date}.js'
            # 添加特定请求头
            headers = {
                'Referer': 'http://www.gfex.com.cn/gfex/rihq/',
                'Origin': 'http://www.gfex.com.cn',
                'Accept': 'application/javascript, text/javascript, */*; q=0.01',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            self.session.headers.update(headers)
            
            response = self.session.get(url, timeout=30)

            if response.status_code != 200:
                print(f"[GFEX] API请求失败: {response.status_code}")
                return None

            content = response.text.strip()
            
            # 检查是否返回了HTML页面（WAF保护）
            if content.startswith('<!DOCTYPE html>') or content.startswith('<html'):
                print("[GFEX] 返回了HTML页面（可能被WAF拦截），尝试降级")
                return self._fallback_to_akshare(trade_date)

            # 去除JS变量包装: var xxx = {...};
            if content.startswith('var '):
                eq_pos = content.find('=')
                if eq_pos > 0:
                    content = content[eq_pos + 1:].strip()
                if content.endswith(';'):
                    content = content[:-1].strip()

            if not content:
                print("[GFEX] 空响应")
                return None

            # 尝试解析JSON
            try:
                json_data = json.loads(content)
            except json.JSONDecodeError:
                print("[GFEX] JSON解析失败，尝试降级")
                return self._fallback_to_akshare(trade_date)

            records = []

            # 处理两种可能的响应格式
            if isinstance(json_data, list):
                items = json_data
            elif isinstance(json_data, dict):
                # 单条数据或嵌套结构
                if any(k in json_data for k in ('symbol', 'open', 'close')):
                    items = [json_data]
                else:
                    # 尝试找第一个数组值
                    for v in json_data.values():
                        if isinstance(v, list):
                            items = v
                            break
                    else:
                        print("[GFEX] 无法识别数据结构")
                        return None
            else:
                print("[GFEX] 无法解析的JSON类型")
                return None

            for item in items:
                if not isinstance(item, dict):
                    continue
                symbol = item.get('symbol', '') or item.get('PRODUCTID', '') or ''
                if not symbol:
                    continue

                records.append({
                    'exchange': 'GFEX',
                    'symbol': symbol,
                    'trade_date': trade_date,
                    'open': float(item.get('open', 0) or item.get('OPENPRICE', 0) or 0),
                    'high': float(item.get('high', 0) or item.get('HIGHESTPRICE', 0) or 0),
                    'low': float(item.get('low', 0) or item.get('LOWESTPRICE', 0) or 0),
                    'close': float(item.get('close', 0) or item.get('CLOSEPRICE', 0) or 0),
                    'settle': float(item.get('settle', 0) or item.get('SETTLEMENTPRICE', 0) or 0),
                    'volume': int(float(item.get('volume', 0) or item.get('VOLUME', 0) or 0)),
                    'open_interest': int(float(item.get('openInterest', 0) or item.get('OPENINTEREST', 0) or 0)),
                    'turnover': float(item.get('turnover', 0) or item.get('TURNOVER', 0) or 0),
                    'source': 'GFEX官方API'
                })

            if records:
                df = pd.DataFrame(records)
                print(f"[GFEX] 成功: {len(df)}条")
                self._save_to_db(df)
                return df
            else:
                print("[GFEX] 无有效记录")
                return None

        except Exception as e:
            print(f"[GFEX] 异常: {e}")
            # 尝试降级到AKShare或TqSdk
            print(f"[GFEX] 尝试降级...")
            fallback_df = self._fallback_to_akshare(trade_date)
            if fallback_df is None:
                fallback_df = self._fallback_to_tqsdk(trade_date)
            return fallback_df

    # ==================== 统一接口 ====================
    def get_all_exchange_data(self, trade_date: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        获取所有交易所的日线数据（串行获取，间隔1秒）

        如果所有交易所都返回None，则整体返回None。
        至少有一个交易所成功时，合并返回所有数据。

        Args:
            trade_date: 交易日期，格式：YYYYMMDD
            use_cache: 是否优先使用数据库缓存

        Returns:
            DataFrame or None
        """
        all_data = []

        exchanges = [
            ('DCE', self.get_dce_daily_data),
            ('SHFE', self.get_shfe_daily_data),
            ('CZCE', self.get_czce_daily_data),
            ('CFFEX', self.get_cffex_daily_data),
            ('GFEX', self.get_gfex_daily_data),
        ]

        success_count = 0
        failure_count = 0

        for name, func in exchanges:
            try:
                print(f"\n[正在获取] {name}数据...")
                df = func(trade_date, use_cache)
                if df is not None and len(df) > 0:
                    all_data.append(df)
                    success_count += 1
                    print(f"[{name}] ✓ {len(df)}条")
                else:
                    failure_count += 1
                    print(f"[{name}] - 无数据")
            except Exception as e:
                failure_count += 1
                print(f"[{name}] ✗ 异常: {e}")

            # 间隔1秒避免触发限流
            time.sleep(1)

        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            print(f"\n[完成] {success_count}/5交易所成功, {len(result)}条记录")
            # 数据完整性验证：检查是否有极端异常值
            _bad_close = (result['close'] <= 0).sum()
            _bad_volume = (result['volume'] < 0).sum()
            if _bad_close > 0:
                print(f"[WARN] 有 {_bad_close} 条记录的收盘价<=0，将被过滤")
                result = result[result['close'] > 0]
            if _bad_volume > 0:
                print(f"[WARN] 有 {_bad_volume} 条记录的成交量<0，将被修正")
                result.loc[result['volume'] < 0, 'volume'] = 0
            print(f"[验证] 清洗后 {len(result)} 条有效记录")
            return result
        else:
            print(f"\n[失败] 所有5个交易所均无数据返回")
            return None

    def is_trading_day(self, date_str: str) -> bool:
        """
        判断是否为交易日。
        周末和已知法定节假日返回False。
        """
        dt = datetime.strptime(date_str, '%Y%m%d')
        if dt.weekday() >= 5:  # 周末
            return False
        if date_str in _KNOWN_HOLIDAYS:
            return False
        return True

    def get_latest_trading_day(self, max_lookback: int = 15) -> str:
        """
        获取最近交易日。
        考虑周末和中国法定节假日，向前最多查找max_lookback天。

        Args:
            max_lookback: 最大向前查找天数

        Returns:
            YYYYMMDD格式的最近交易日
        """
        today = datetime.now()
        for offset in range(max_lookback):
            d = today - timedelta(days=offset)
            date_str = d.strftime('%Y%m%d')
            if self.is_trading_day(date_str):
                return date_str

        # 兜底：使用今天之前最近的非节假日工作日
        for offset in range(max_lookback, max_lookback * 2):
            d = today - timedelta(days=offset)
            if d.weekday() < 5:  # 至少是工作日
                return d.strftime('%Y%m%d')

        return today.strftime('%Y%m%d')

    # ==================== 历史数据批量采集 ====================
    def batch_collect(self, start_date: str, end_date: Optional[str] = None):
        """
        批量采集历史数据（仅交易日，已缓存跳过）

        性能优化：每个交易日仅一次数据库连接检查缓存，
        每个交易所之间间隔1秒，每天之间间隔2秒。

        Args:
            start_date: 起始日期 YYYYMMDD
            end_date: 结束日期（默认当天）
        """
        if end_date is None:
            end_date = self.get_latest_trading_day()

        # 预计算交易日列表（排除周末和已知节假日）
        all_dates = []
        d = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        while d <= end_dt:
            date_str = d.strftime('%Y%m%d')
            if self.is_trading_day(date_str):
                all_dates.append(date_str)
            d += timedelta(days=1)

        total = len(all_dates)
        cached_count = 0
        success = 0
        fail = 0

        print(f"\n批量采集: {start_date} → {end_date}, 共{total}个交易日")

        for i, trade_date in enumerate(all_dates):
            # 检查是否已缓存（批量检查效率更高）
            cached = self._read_from_db(trade_date)
            if cached is not None:
                cached_count += 1
                if (i + 1) % 10 == 0:
                    print(f"[{i+1}/{total}] {trade_date}: 已缓存 ({len(cached)}条)")
                continue

            print(f"[{i+1}/{total}] {trade_date}: 正在采集...")
            try:
                df = self.get_all_exchange_data(trade_date, use_cache=False)
                if df is not None:
                    success += 1
                    print(f"  → {len(df)}条")
                else:
                    fail += 1
                    print(f"  → 无数据")
            except Exception as e:
                fail += 1
                print(f"  → 异常: {e}")

            time.sleep(2)

        print(f"\n批量采集完成: 成功{success}, 失败{fail}, 已缓存{cached_count}, 共{total}")


def main():
    """测试/日常执行 — 使用DuckDB自动缓存"""
    collector = ExchangeDataCollector()

    # 检查数据库状态
    total_records = collector.get_cached_count()
    cached_dates = collector.get_cached_dates()
    print(f"[数据库] {collector.db_path}")
    print(f"[数据库] 总记录数: {total_records}")
    print(f"[数据库] 已缓存交易日: {len(cached_dates)}个")

    # 获取最新交易日数据
    trade_date = collector.get_latest_trading_day()
    print(f"\n[交易日] {trade_date}")

    df = collector.get_all_exchange_data(trade_date, use_cache=True)

    if df is not None:
        print(f"\n[概览] 总记录数: {len(df)}")
        print(f"[概览] 交易所分布:")
        print(df['exchange'].value_counts().to_string())
    else:
        print(f"\n[注意] {trade_date} 无数据（可能非交易日或休市）")


if __name__ == '__main__':
    main()
