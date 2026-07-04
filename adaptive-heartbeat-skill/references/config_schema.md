# monitor_config.json — Full Schema Reference

Version: 3.0.0

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| version | string | yes | Schema version, "3.0.0" |
| name | string | yes | Monitor system display name |
| description | string | no | Human readable description |
| timezone | string | yes | IANA timezone, e.g. "Asia/Shanghai" |
| monitor_root | string | yes | Directory where monitor_config.json resides (for relative paths) |
| products | object | yes | Keyed by product code, value = Product |
| data_sources | array[DataSource] | yes | Ordered by priority within each category |
| focus_types | object | yes | Keyed by focus type id, value = FocusType |
| focus_chains | array[FocusChain] | no | Inter-focus resonance rules |
| tech_signals | array[TechSignal] | no | Technical signal definitions |
| link_metrics | array[LinkMetric] | no | Cross-product derived metrics |
| scoring | Scoring | yes | Scoring weights and thresholds |
| thresholds | Thresholds | yes | Alert and extreme event conditions |
| report_path | string | yes | Absolute report output root directory |
| report_name_format | string | yes | Filename template, {name} {date} {time} supported |
| schedule | Schedule | yes | Adaptive scheduling config |
| red_rules | RedRules | no | Override default hard rules |
| initial_state | object | no | Default state.json values if file is missing |
| user_feedback | object | no | Feedback learning config |

## Product

```json
{
  "name": "品种中文名",
  "exchange": "交易所",
  "unit": "价格单位",
  "lot_size": 10,
  "url_params": {
    "cngold": "luowengang",
    "eastmoney": "RB"
  }
}
```

`url_params` keys match `{param}` placeholders in DataSource `url_template`.

## DataSource

```json
{
  "id": "unique_source_id",
  "category": "realtime|fundamental|news",
  "priority": 1,
  "enabled": true,
  "reliability": 85,
  "url_template": "https://example.com/{param}.html",
  "url_static": null,
  "extraction_type": "html_parse|json|web_search",
  "field_mappings": {
    "price_field": "css_selector_or_json_path",
    "change_pct_field": "..."
  },
  "refresh_minutes": 5,
  "max_staleness_min": 30,
  "max_deviation_pct": 5,
  "note": "human note"
}
```

If `url_template` is null and `url_static` is set, uses static URL.
If `extraction_type` is "web_search", uses `query_template` instead of URL.

## FocusType

```json
{
  "trigger_conditions": [
    {
      "kind": "keyword|price_change|fundamental_change|supply_chain_resonance",
      "keywords": ["关键词1", "关键词2"],
      "source_ids": ["news_source_id"],
      "product": "RB",
      "threshold_pct": 3.0,
      "direction": "above|below|either",
      "products": ["I", "J"],
      "confidence_formula": "0.9 * min(abs(change_pct) / 5, 1.0)"
    }
  ],
  "impact_base": 0.4,
  "impact_bonuses": [
    {
      "condition": "price_change > 5",
      "boost": 0.2
    }
  ],
  "check_interval_high": 30,
  "check_interval_medium": 60,
  "check_interval_low": 120
}
```

## FocusChain

```json
{
  "name": "profit_squeeze_resonance",
  "conditions": [
    {
      "kind": "product_compare",
      "products": ["I", "J"],
      "operator": "all_above",
      "threshold_pct": 3.0
    },
    {
      "kind": "product_compare",
      "products": ["RB"],
      "operator": "all_below",
      "threshold_pct": 0.5
    }
  ],
  "target_focus": "profit_margin",
  "confidence_boost": 0.2
}
```

## TechSignal

```json
{
  "id": "T1",
  "name": "趋势延续",
  "type": "trend|breakout|divergence|position|spread|inventory",
  "condition": {
    "kind": "multi_day_trend",
    "products": ["RB", "HC"],
    "days": 3,
    "min_pct_per_day": 1.0,
    "direction": "same"
  },
  "weight": 0.3,
  "requires_close": true
}
```

## LinkMetric

```json
{
  "name": "螺矿比",
  "code": "rebar_iron_ratio",
  "formula": "RB_price / I_price",
  "products": ["RB", "I"],
  "normal_range": [3.8, 5.0],
  "extreme_low": 3.5,
  "extreme_high": 5.5,
  "unit": "ratio"
}
```

## Scoring

```json
{
  "novelty_weight": 0.5,
  "impact_weight": 0.2,
  "reliability_weight": 0.2,
  "tech_signal_weight": 0.1,
  "push_threshold": 0.55,
  "calibration_range": [0.35, 0.75]
}
```

## Thresholds

```json
{
  "extreme_conditions": [
    {
      "kind": "price_change",
      "product": "RB",
      "threshold_pct": 5.0,
      "direction": "either"
    },
    {
      "kind": "keyword",
      "keywords": ["限产令", "房地产重磅"],
      "source_ids": ["news_source_id"]
    }
  ],
  "novelty_penalty_hours": 6,
  "novelty_hard_penalty": 0.2,
  "trading_only_checks": true
}
```

## Schedule

```json
{
  "default_interval_min": 120,
  "non_trading_interval_min": 240,
  "urgent_threshold": 0.7,
  "downgrade_threshold": 0.3,
  "max_urgent_cron_hours": 6,
  "calibration_frequency": 10
}
```

## RedRules (optional, overrides defaults)

```json
{
  "no_fabricated_data": true,
  "right_side_trading": true,
  "min_quantifiable_signals": 2,
  "primary_timeframe": "daily_4h",
  "disclaimer_required": true,
  "language": "zh-CN",
  "no_emoji": true,
  "novelty_guard_enabled": true
}
```
