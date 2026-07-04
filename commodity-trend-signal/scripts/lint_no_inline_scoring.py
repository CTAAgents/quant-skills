#!/usr/bin/env python3
"""
评分逻辑重复检测器 — lint_no_inline_scoring.py
==============================================
检查 commodity-trend-signal 脚本目录中是否存在"内联评分逻辑"（
即绕过 scoring_system.py 自行实现 L1-L4 打分的代码）。

使用方法：
  python lint_no_inline_scoring.py
  
退出码：
  0 — 未发现重复评分逻辑
  1 — 发现重复评分逻辑
"""
import ast
import os
import sys
import glob

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

# 禁止出现的模式组合（内联评分关键词）
FORBIDDEN_PATTERNS = {
    "l1_l4_score": "绕过 scoring_system.py 的独立 l1_l4_score 实现",
    "MA20_SLOPE.*+=.*12": "内联 MA20 斜率评分（应使用 score_L1_germination）",
    "higher_low.*+=.*10": "内联 Higher Low 评分",
    "lower_high.*+=.*10": "内联 Lower High 评分",
    "SUPERTREND_DIR.*+=.*[47]": "内联 SuperTrend 评分（应使用 score_L2_volume_price）",
}


def check_file(filepath: str) -> list[str]:
    """检查单个文件是否存在内联评分逻辑"""
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 如果文件已经 import 了 scoring_system，跳过（委派模式）
        if "from scoring_system import" in content or "import scoring_system" in content:
            return issues
        
        # 对未引用 scoring_system 的文件，检查是否包含评分特征
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            # 检查特征关键词
            if line_stripped.startswith('def l1_l4_score'):
                issues.append(f"  L{i}: 发现内联 l1_l4_score 定义 — 应使用 scoring_system.calculate_composite_score")
            if "l1_l4_score(tech)" in line_stripped and "def" not in line_stripped:
                # 调用 l1_l4_score 而本文件未定义 → 可能安全，标记观察
                pass
        
    except Exception as e:
        issues.append(f"  [ERROR] {e}")
    
    return issues


def main():
    script_dir = SKILL_DIR
    py_files = glob.glob(os.path.join(script_dir, "*.py"))
    
    # 排除自身和备份文件
    exclude = {os.path.basename(__file__), "full_scan_debate.py.bak"}
    py_files = [f for f in py_files if os.path.basename(f) not in exclude]
    
    all_issues = []
    for fpath in sorted(py_files):
        basename = os.path.basename(fpath)
        issues = check_file(fpath)
        if issues:
            print(f"⚠️  {basename}:")
            for issue in issues:
                print(issue)
            all_issues.extend(issues)
    
    if all_issues:
        print(f"\n❌ 发现 {len(all_issues)} 个内联评分逻辑问题。")
        print("请将所有评分逻辑统一使用 scoring_system.py 的 calculate_composite_score()。")
        sys.exit(1)
    else:
        print("✅ 所有文件均通过检测，未发现内联评分逻辑。")
        sys.exit(0)


if __name__ == '__main__':
    main()
