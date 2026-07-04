#!/usr/bin/env python3
"""
NL2FQL Engine v2.0 - Natural Language to Futures Query Language
将自然语言查询转换为结构化的期货查询语句（FQL）

改进：
- 智能品种识别：区分"铜"（已知）和"铜锌合金"（未知）
- 完整价差对支持
- 更准确的实体抽取
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class QueryType(Enum):
    """查询类型"""
    QUOTE = "quote"              # 行情查询
    SPREAD = "spread"            # 价差查询
    RATIO = "ratio"              # 比价查询
    TERM_STRUCTURE = "term_structure"  # 期限结构
    OI_RANKING = "oi_ranking"    # 持仓排名
    WAREHOUSE = "warehouse"      # 仓单查询
    DELIVERY = "delivery"        # 交割查询
    NEWS = "news"                # 资讯查询
    COMPARE = "compare"          # 品种对比
    AGGREGATE = "aggregate"      # 聚合统计
    UNKNOWN = "unknown"          # 未知查询


class AggFunc(Enum):
    """聚合函数"""
    AVG = "avg"
    SUM = "sum"
    MAX = "max"
    MIN = "min"
    STD = "std"
    COUNT = "count"
    CHANGE = "change"            # 涨跌幅
    VOLATILITY = "volatility"    # 波动率


@dataclass
class FQLQuery:
    """FQL 查询对象"""
    query_type: QueryType
    varieties: List[str] = field(default_factory=list)
    contract_types: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    relative_time: Optional[str] = None
    agg_func: Optional[AggFunc] = None
    limit: Optional[int] = None
    order_by: Optional[str] = None
    order_desc: bool = False
    filters: Dict[str, Any] = field(default_factory=dict)
    spread_pair: Optional[tuple[str, ...]] = None
    raw_text: str = ""
    parse_errors: List[str] = field(default_factory=list)

    def to_sql(self) -> str:
        """
        转换为 SQL 语句（已废弃）
        
        实际数据通过 MultiSourceAdapter 获取，本方法仅作参考。
        DuckDB 表结构：oi_ranking / warehouse / futurs_news / term_structure / query_cache。
        不再从 to_dict() 调用。
        """
        query_type_name = self.query_type.value if self.query_type else "unknown"
        variety_str = ", ".join(self.varieties) if self.varieties else "*"
        return f"-- FQL: {query_type_name} / {variety_str} / 通过 MultiSourceAdapter 执行"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "query_type": self.query_type.value,
            "varieties": self.varieties,
            "contract_types": self.contract_types,
            "metrics": self.metrics,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "relative_time": self.relative_time,
            "agg_func": self.agg_func.value if self.agg_func else None,
            "limit": self.limit,
            "order_by": self.order_by,
            "order_desc": self.order_desc,
            "filters": self.filters,
            "spread_pair": self.spread_pair,
            "raw_text": self.raw_text,
            "parse_errors": self.parse_errors
        }


class NL2FQLEngine:
    """NL2FQL 引擎 - 自然语言转期货查询语句"""

    def __init__(self):
        # 品种词典（从 varieties.yaml 加载）
        self.variety_aliases = self._load_variety_aliases()
        
        # 构建标准品种代码集合（用于验证）
        self.valid_varieties: Set[str] = set(self.variety_aliases.values())
        
        # 构建中文别名到代码的映射（只包含中文别名，排除单字母）
        self.chinese_aliases: Dict[str, str] = {}
        for alias, code in self.variety_aliases.items():
            # 只保留中文别名（包含中文字符）或长度>1的英文别名
            if self._contains_chinese(alias) or (len(alias) > 1 and alias.isalpha()):
                self.chinese_aliases[alias] = code

        # 时间关键词映射
        self.time_keywords = {
            "今天": ("today", 0),
            "今日": ("today", 0),
            "昨天": ("yesterday", 1),
            "昨日": ("yesterday", 1),
            "最近": ("last_n", 5),
            "近期": ("last_n", 5),
            "本周": ("this_week", 0),
            "上周": ("last_week", 1),
            "本月": ("this_month", 0),
            "上月": ("last_month", 1),
            "近一周": ("last_n", 7),
            "近一个月": ("last_n", 30),
            "近30天": ("last_n", 30),
            "近5天": ("last_n", 5),
            "近10天": ("last_n", 10),
        }

        # 指标关键词映射
        self.metric_keywords = {
            "价格": "close",
            "收盘价": "close",
            "收盘": "close",
            "开盘价": "open",
            "开盘": "open",
            "最高价": "high",
            "最高": "high",
            "最低价": "low",
            "最低": "low",
            "成交量": "volume",
            "成交": "volume",
            "持仓量": "open_interest",
            "持仓": "open_interest",
            "结算价": "settle",
            "结算": "settle",
            "涨跌幅": "change_pct",
            "涨跌": "change_pct",
            "波动率": "volatility",
        }

        # 查询类型关键词
        self.query_type_keywords = {
            "价差": QueryType.SPREAD,
            "比价": QueryType.RATIO,
            "期限结构": QueryType.TERM_STRUCTURE,
            "持仓排名": QueryType.OI_RANKING,
            "前20": QueryType.OI_RANKING,
            "仓单": QueryType.WAREHOUSE,
            "交割": QueryType.DELIVERY,
            "资讯": QueryType.NEWS,
            "新闻": QueryType.NEWS,
            "公告": QueryType.NEWS,
            "对比": QueryType.COMPARE,
            "比较": QueryType.COMPARE,
        }

        # 聚合函数关键词
        self.agg_keywords = {
            "平均": AggFunc.AVG,
            "均值": AggFunc.AVG,
            "总计": AggFunc.SUM,
            "合计": AggFunc.SUM,
            "最高": AggFunc.MAX,
            "最大": AggFunc.MAX,
            "最低": AggFunc.MIN,
            "最小": AggFunc.MIN,
            "波动": AggFunc.STD,
            "标准差": AggFunc.STD,
        }

        # 常见价差对（中文名 -> (品种1, 品种2)）
        # 注意：个别多腿策略（钢厂利润、石化利润）为3元组，下游代码应兼容
        self.spread_pairs = {
            # 黑色系
            "螺卷差": ("RB", "HC"),
            "螺矿比": ("RB", "I"),
            "焦炭焦煤比": ("J", "JM"),
            "焦煤焦炭比": ("JM", "J"),
            "卷螺差": ("HC", "RB"),
            "铁矿焦炭比": ("I", "J"),
            
            # 有色金属
            "铜锌比": ("CU", "ZN"),
            "铜铝比": ("CU", "AL"),
            "锌铅比": ("ZN", "PB"),
            "镍锡比": ("NI", "SN"),
            
            # 贵金属
            "金银比": ("AU", "AG"),
            "金铂比": ("AU", "PT"),
            
            # 农产品
            "豆棕差": ("M", "P"),
            "油粕比": ("Y", "M"),
            "豆菜粕差": ("M", "RM"),
            "菜豆油差": ("OI", "Y"),
            "玉米淀粉差": ("C", "CS"),
            "鸡蛋生猪比": ("JD", "LH"),
            
            # 能源化工
            "原油燃油差": ("SC", "FU"),
            "原油沥青差": ("SC", "BU"),
            "甲醇乙二醇比": ("MA", "EG"),
            "PTA甲醇比": ("TA", "MA"),
            "塑料PP比": ("L", "PP"),
            "PVC塑料比": ("V", "L"),
            "纯碱玻璃差": ("SA", "FG"),
            
            # 跨品种套利
            "钢厂利润": ("RB", "I", "J"),  # 螺纹 - 铁矿 - 焦炭
            "石化利润": ("SC", "L", "PP"),  # 原油 - 塑料 - PP
        }

    def _contains_chinese(self, text: str) -> bool:
        """检查文本是否包含中文字符"""
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return True
        return False

    def _load_variety_aliases(self) -> Dict[str, str]:
        """
        从 varieties.yaml 加载品种别名映射。
        文件不可用时回退到内建词典。
        """
        # 尝试从 YAML 文件加载（单一事实源）
        yaml_path = Path(__file__).parent.parent / "references" / "varieties.yaml"
        if yaml_path.exists():
            try:
                import yaml
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                result = {}
                for v in data.get("varieties", []):
                    code = v["code"]
                    result[v["name"]] = code
                    for alias in v.get("aliases", []):
                        if alias not in result:
                            result[alias] = code
                if result:
                    return result
            except Exception:
                pass

        # 回退：内建词典（与 varieties.yaml 同步维护）
        return {
            # SHFE 上期所
            "铜": "CU", "沪铜": "CU", "阴极铜": "CU",
            "铝": "AL", "沪铝": "AL", "铝锭": "AL",
            "锌": "ZN", "沪锌": "ZN",
            "铅": "PB", "沪铅": "PB",
            "镍": "NI", "沪镍": "NI",
            "锡": "SN", "沪锡": "SN",
            "黄金": "AU", "沪金": "AU", "金": "AU",
            "白银": "AG", "沪银": "AG", "银": "AG",
            "螺纹": "RB", "螺纹钢": "RB", "钢": "RB",
            "热卷": "HC", "热轧": "HC",
            "不锈钢": "SS",
            "橡胶": "RU", "天胶": "RU", "沪胶": "RU",
            "燃油": "FU", "燃料油": "FU",
            "沥青": "BU",
            "纸浆": "SP", "木浆": "SP",
            "氧化铝": "AO",
            # DCE 大商所
            "豆一": "A", "黄大豆1号": "A",
            "豆二": "B", "黄大豆2号": "B",
            "豆粕": "M",
            "豆油": "Y",
            "棕榈油": "P", "棕榈": "P",
            "玉米": "C",
            "淀粉": "CS", "玉米淀粉": "CS",
            "铁矿": "I", "铁矿石": "I",
            "焦炭": "J",
            "焦煤": "JM", "主焦煤": "JM",
            "塑料": "L", "LLDPE": "L", "聚乙烯": "L",
            "PVC": "V", "聚氯乙烯": "V",
            "PP": "PP", "聚丙烯": "PP",
            "乙二醇": "EG", "MEG": "EG",
            "苯乙烯": "EB",
            "LPG": "PG", "液化气": "PG", "液化石油气": "PG",
            "鸡蛋": "JD",
            "生猪": "LH", "猪": "LH",
            # CZCE 郑商所
            "苹果": "AP",
            "棉花": "CF", "郑棉": "CF",
            "棉纱": "CY",
            "红枣": "CJ",
            "玻璃": "FG",
            "纯碱": "SA", "苏打": "SA",
            "烧碱": "SH", "液碱": "SH",
            "甲醇": "MA", "郑醇": "MA",
            "PTA": "TA",
            "尿素": "UR",
            "短纤": "PF", "涤纶短纤": "PF",
            "花生": "PK",
            "菜油": "OI", "菜籽油": "OI", "郑油": "OI",
            "菜粕": "RM", "菜籽粕": "RM",
            "白糖": "SR", "郑糖": "SR",
            "锰硅": "SM", "硅锰": "SM",
            "硅铁": "SF",
            "动力煤": "ZC", "动煤": "ZC", "郑煤": "ZC",
            # GFEX 广期所
            "工业硅": "SI", "硅": "SI",
            "碳酸锂": "LC", "锂": "LC",
            "多晶硅": "PS", "硅料": "PS",
            # INE 上期能源
            "原油": "SC", "上期原油": "SC",
            "低硫燃": "LU", "低硫燃料油": "LU",
            "20号胶": "NR", "标胶": "NR",
            "国际铜": "BC",
            # CFFEX 中金所
            "沪深300": "IF", "沪深300期货": "IF",
            "中证500": "IC", "中证500期货": "IC",
            "中证1000": "IM", "中证1000期货": "IM",
            "上证50": "IH", "上证50期货": "IH",
            "十年债": "T", "10年国债": "T",
            "五年债": "TF", "5年国债": "TF",
            "二年债": "TS", "2年国债": "TS",
            "三十年债": "TL", "30年国债": "TL",
        }

    def parse(self, text: str) -> FQLQuery:
        """
        解析自然语言，生成 FQL 查询

        Args:
            text: 自然语言文本

        Returns:
            FQLQuery 对象
        """
        query = FQLQuery(raw_text=text, query_type=QueryType.QUOTE)

        # 1. 提取查询类型（先于品种提取，因为价差对需要特殊处理）
        query_type = self._extract_query_type(text)
        query.query_type = query_type

        # 2. 提取品种（使用智能匹配）
        varieties, is_valid = self._extract_varieties_smart(text, query_type)
        query.varieties = varieties

        # 3. 如果品种无效，标记为未知
        if not is_valid and not varieties:
            query.parse_errors.append("品种未识别，请重新输入")

        # 4. 提取时间范围
        start_date, end_date, relative_time = self._extract_time(text)
        query.start_date = start_date
        query.end_date = end_date
        query.relative_time = relative_time

        # 5. 提取指标
        metrics = self._extract_metrics(text)
        query.metrics = metrics

        # 6. 提取聚合函数
        agg_func = self._extract_agg_func(text)
        query.agg_func = agg_func

        # 7. 提取价差对
        if query_type in (QueryType.SPREAD, QueryType.RATIO):
            pair = self._extract_spread_pair(text)
            if pair:
                query.spread_pair = pair
                # 确保价差对的品种也在 varieties 中
                for v in pair:
                    if v not in query.varieties:
                        query.varieties.append(v)

        # 8. 提取数量限制
        limit = self._extract_limit(text)
        if limit:
            query.limit = limit

        # 9. 设置默认合约类型
        if not query.contract_types:
            query.contract_types = ["main"]

        return query

    def _extract_varieties_smart(self, text: str, query_type: QueryType) -> Tuple[List[str], bool]:
        """
        智能提取品种
        
        规则：
        1. 优先匹配完整的中文别名（长词优先）
        2. 对于英文代码，必须是独立的单词（前后是空格或标点）
        3. 如果输入包含未知成分，返回空列表
        
        Returns:
            (品种列表, 是否有效)
        """
        varieties = []
        matched_positions = set()  # 记录已匹配的位置

        # Step 1: 按别名长度排序，优先匹配长的中文别名
        sorted_chinese = sorted(self.chinese_aliases.items(), key=lambda x: len(x[0]), reverse=True)
        
        for alias, code in sorted_chinese:
            # 查找所有出现位置
            start = 0
            while True:
                pos = text.find(alias, start)
                if pos == -1:
                    break
                
                # 检查是否与已匹配位置重叠
                alias_range = set(range(pos, pos + len(alias)))
                if not alias_range.intersection(matched_positions):
                    # 检查前后字符是否是合理的边界
                    if self._is_valid_boundary(text, pos, len(alias)):
                        if code not in varieties:
                            varieties.append(code)
                        matched_positions.update(alias_range)
                
                start = pos + 1

        # Step 2: 尝试匹配英文代码（必须是独立单词）
        # 注意：Python 3 Unicode 模式下 \w 包含中文字符，导致 \b 无法正确识别英文-
        # 中文边界。使用 ASCII 版单词边界避免此问题。
        if not varieties:
            # 匹配 2-3 位大写字母（前后为非 [A-Za-z0-9] 字符）
            ascii_boundary = r'(?<![A-Za-z0-9])([A-Z]{2,3})(?![A-Za-z0-9])'
            for match in re.finditer(ascii_boundary, text):
                code = match.group(1)
                if code in self.valid_varieties:
                    # 检查是否与已匹配位置重叠
                    match_range = set(range(match.start(), match.end()))
                    if not match_range.intersection(matched_positions):
                        varieties.append(code)
                        matched_positions.update(match_range)

        # Step 3: 验证提取的品种是否有效
        if varieties:
            # 过滤掉无效的品种代码
            valid_varieties = [v for v in varieties if v in self.valid_varieties]
            
            # Step 3.5: 检查是否是复合词（多个品种紧密相连形成未知词）
            # 例如："铜锌合金" 包含 "铜"、"锌"、"金"，但应该拒绝
            if len(valid_varieties) > 1:
                # 检查品种之间是否有分隔符
                has_separator = self._has_variety_separator(text, matched_positions)
                if not has_separator:
                    # 没有分隔符，可能是复合词，需要进一步检查
                    # 计算匹配的字符数占输入的比例
                    matched_char_count = len(matched_positions)
                    # 去掉查询关键词后的字符数
                    query_keywords = ["行情", "价格", "最新", "主力", "仓单", "持仓", "排名", 
                                      "期限结构", "公告", "新闻", "资讯", "价差", "比价"]
                    text_without_keywords = text
                    for kw in query_keywords:
                        text_without_keywords = text_without_keywords.replace(kw, "")
                    
                    # 如果匹配的字符数占去掉关键词后文本的比例很高，可能是复合词
                    if len(text_without_keywords) > 0:
                        match_ratio = matched_char_count / len(text_without_keywords)
                        if match_ratio >= 0.5:
                            # 大部分字符都被匹配为品种，可能是复合词
                            # 检查是否是已知的复合词
                            if not self._is_known_compound(text):
                                return [], False
            
            return valid_varieties, True

        # Step 4: 对于价差查询，检查是否包含价差对名称
        if query_type == QueryType.SPREAD:
            for pair_name, pair in self.spread_pairs.items():
                if pair_name in text:
                    return list(pair), True

        return [], False

    def _has_variety_separator(self, text: str, matched_positions: set) -> bool:
        """检查品种之间是否有分隔符（如'和'、'与'、空格、逗号等）"""
        if not matched_positions:
            return False
        
        # 找到所有匹配位置的范围
        sorted_positions = sorted(matched_positions)
        
        # 检查匹配位置之间是否有非匹配字符
        for i in range(len(sorted_positions) - 1):
            pos1 = sorted_positions[i]
            pos2 = sorted_positions[i + 1]
            # 如果两个匹配位置不相邻，中间有其他字符
            if pos2 - pos1 > 1:
                # 检查中间的字符是否是分隔符
                between_chars = text[pos1+1:pos2]
                # 常见分隔符：空格、逗号、和、与、及
                separators = [' ', '，', ',', '和', '与', '及', '、', '/', '-']
                for sep in separators:
                    if sep in between_chars:
                        return True
        
        return False

    def _is_known_compound(self, text: str) -> bool:
        """检查是否是已知的复合词（如'螺纹钢'）"""
        # 已知的复合词列表（这些是有效的品种别名）
        known_compounds = [
            "螺纹钢", "热轧卷板", "不锈钢", "天然橡胶", "石油沥青",
            "线性低密度聚乙烯", "聚氯乙烯", "聚丙烯", "乙二醇", "苯乙烯",
            "液化石油气", "黄大豆1号", "黄大豆2号", "玉米淀粉",
            "对苯二甲酸", "涤纶短纤", "菜籽油", "菜籽粕",
            "工业硅", "碳酸锂", "多晶硅", "低硫燃料油",
        ]
        for compound in known_compounds:
            if compound in text:
                return True
        return False

    def _is_valid_boundary(self, text: str, pos: int, length: int) -> bool:
        """
        检查匹配位置是否是有效的词边界
        
        规则：
        1. 对于中文别名，不需要严格的边界检查（中文以字符为单位）
        2. 只检查是否是更长有效别名的一部分
        3. 对于单字品种（如"铜"），如果前面是中文前缀（如"沪"），检查是否形成更长别名
        """
        matched_text = text[pos:pos+length]
        
        # 检查前面的字符是否形成更长的有效别名
        if pos > 0:
            prev_char = text[pos - 1]
            # 如果前一个字符是中文，检查是否形成更长的别名
            if self._contains_chinese(prev_char):
                # 检查是否是更长别名的一部分（如"沪铜"中的"铜"）
                for alias in self.chinese_aliases:
                    if (alias != matched_text and 
                        alias.endswith(matched_text) and 
                        len(alias) > length):
                        # 检查前面的字符是否能形成这个更长的别名
                        prefix_len = len(alias) - length
                        if pos >= prefix_len:
                            potential_prefix = text[pos-prefix_len:pos]
                            if potential_prefix + matched_text == alias:
                                return False  # 是更长别名的一部分，跳过
        
        return True

    def _extract_query_type(self, text: str) -> QueryType:
        """提取查询类型"""
        # 先检查价差对名称（如"螺卷差"）
        for pair_name in self.spread_pairs.keys():
            if pair_name in text:
                return QueryType.SPREAD

        # 再检查其他关键词
        for keyword, qtype in self.query_type_keywords.items():
            if keyword in text:
                return qtype
        return QueryType.QUOTE

    def _extract_time(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """提取时间范围"""
        today = datetime.now()

        # 检查相对时间关键词
        for keyword, (time_type, offset) in self.time_keywords.items():
            if keyword in text:
                if time_type == "today":
                    date_str = today.strftime("%Y-%m-%d")
                    return date_str, date_str, "today"
                elif time_type == "yesterday":
                    date_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
                    return date_str, date_str, "yesterday"
                elif time_type == "last_n":
                    start = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
                    end = today.strftime("%Y-%m-%d")
                    return start, end, f"last_{offset}_days"
                elif time_type == "this_week":
                    start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
                    return start, today.strftime("%Y-%m-%d"), "this_week"
                elif time_type == "last_week":
                    end = (today - timedelta(days=today.weekday() + 1)).strftime("%Y-%m-%d")
                    start = (today - timedelta(days=today.weekday() + 7)).strftime("%Y-%m-%d")
                    return start, end, "last_week"
                elif time_type == "this_month":
                    start = today.replace(day=1).strftime("%Y-%m-%d")
                    return start, today.strftime("%Y-%m-%d"), "this_month"
                elif time_type == "last_month":
                    first_of_month = today.replace(day=1)
                    end = (first_of_month - timedelta(days=1)).strftime("%Y-%m-%d")
                    if today.month == 1:
                        start = f"{today.year - 1}-12-01"
                    else:
                        start = f"{today.year}-{today.month - 1:02d}-01"
                    return start, end, "last_month"

        # 检查具体日期格式
        dates = re.findall(r'(\d{4})-(\d{2})-(\d{2})', text)
        if len(dates) >= 2:
            return f"{dates[0][0]}-{dates[0][1]}-{dates[0][2]}", f"{dates[1][0]}-{dates[1][1]}-{dates[1][2]}", None
        elif len(dates) == 1:
            return f"{dates[0][0]}-{dates[0][1]}-{dates[0][2]}", None, None

        # 默认最新
        return None, None, "latest"

    def _extract_metrics(self, text: str) -> List[str]:
        """提取指标"""
        metrics = []
        for keyword, metric in self.metric_keywords.items():
            if keyword in text and metric not in metrics:
                metrics.append(metric)
        return metrics

    def _extract_agg_func(self, text: str) -> Optional[AggFunc]:
        """提取聚合函数"""
        for keyword, func in self.agg_keywords.items():
            if keyword in text:
                return func
        return None

    def _extract_spread_pair(self, text: str) -> Optional[tuple[str, ...]]:
        """提取价差对"""
        # 检查预定义价差对
        for name, pair in self.spread_pairs.items():
            if name in text:
                return pair

        # 检查自定义格式 A-B 或 A/B
        match = re.search(r'([A-Z]{2,3})[-/]([A-Z]{2,3})', text, re.IGNORECASE)
        if match:
            v1, v2 = match.group(1).upper(), match.group(2).upper()
            if v1 in self.valid_varieties and v2 in self.valid_varieties:
                return (v1, v2)

        return None

    def _extract_limit(self, text: str) -> Optional[int]:
        """提取数量限制"""
        match = re.search(r'前(\d+)', text)
        if match:
            return int(match.group(1))

        match = re.search(r'(\d+)条', text)
        if match:
            return int(match.group(1))

        match = re.search(r'(\d+)个', text)
        if match:
            return int(match.group(1))

        return None


def main():
    """测试函数"""
    engine = NL2FQLEngine()

    test_cases = [
        # 已知品种
        ("铜主力合约最近5天的收盘价", ["CU"]),
        ("螺纹钢和热卷的价差", ["RB", "HC"]),
        ("豆粕今日成交量", ["M"]),
        ("铁矿石前20持仓排名", ["I"]),
        ("铜仓单多少", ["CU"]),
        ("黄金白银金银比", ["AU", "AG"]),
        ("沪深300期货最新价格", ["IF"]),
        ("铜的期限结构", ["CU"]),
        ("纯碱行情", ["SA"]),
        ("烧碱行情", ["SH"]),
        # 未知品种（应该拒绝）
        ("铜锌合金行情", []),
        ("XYZ行情", []),
        ("不存在的品种行情", []),
        # 价差查询
        ("螺卷差", ["RB", "HC"]),
        ("RB-HC价差", ["RB", "HC"]),
    ]

    print("NL2FQL Engine Test")
    print("=" * 60)

    for text, expected_varieties in test_cases:
        query = engine.parse(text)
        status = "✓" if set(query.varieties) == set(expected_varieties) else "✗"
        print(f"\n{status} 输入: {text}")
        print(f"  类型: {query.query_type.value}")
        print(f"  品种: {query.varieties} (期望: {expected_varieties})")
        if query.parse_errors:
            print(f"  错误: {query.parse_errors}")


if __name__ == "__main__":
    main()
