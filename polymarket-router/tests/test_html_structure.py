#!/usr/bin/env python3
"""
测试HTML结构分析
"""

import requests
import re

def analyze_html_structure():
    """分析Polyspotter网站的HTML结构"""
    print("分析Polyspotter网站HTML结构...")
    
    # 测试原油页面
    url = "https://polyspotter.com/event/cl-hit-jun-2026"
    print(f"\n访问: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        html = response.text
        print(f"HTML长度: {len(html)} 字符")
        
        # 保存HTML到文件
        with open('polyspotter_crude_oil.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("HTML已保存到 polyspotter_crude_oil.html")
        
        # 分析HTML结构
        print("\nHTML结构分析:")
        
        # 查找市场名称模式
        market_patterns = [
            r'Will Crude Oil \(CL\) hit.*?\$\d[\d,]* by end of June\?',
            r'Will Crude Oil.*?hit.*?\$\d[\d,]*',
            r'Crude Oil.*?\$\d[\d,]*',
            r'Will.*?hit.*?\$\d[\d,]*'
        ]
        
        for pattern in market_patterns:
            matches = re.findall(pattern, html)
            if matches:
                print(f"模式 '{pattern[:50]}...' 找到 {len(matches)} 个匹配")
                for i, match in enumerate(matches[:3]):  # 只显示前3个
                    print(f"  {i+1}. {match[:100]}...")
        
        # 查找信号和成交量模式
        signal_patterns = [
            r'\d+ signals? across \d+ markets?',
            r'\$\$[\d,]+ tracked',
            r'signal.*?tracked',
            r'\d+.*?signal.*?tracked'
        ]
        
        print("\n信号模式分析:")
        for pattern in signal_patterns:
            matches = re.findall(pattern, html)
            if matches:
                print(f"模式 '{pattern[:50]}...' 找到 {len(matches)} 个匹配")
                for i, match in enumerate(matches[:3]):
                    print(f"  {i+1}. {match[:100]}...")
        
        # 查找JSON数据
        print("\nJSON数据分析:")
        json_patterns = [
            r'self\.__next_f\.push\(\[1,".*?"\]\)',
            r'<script.*?>.*?</script>',
            r'window\.__INITIAL_STATE__.*?=.*?;'
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            if matches:
                print(f"模式 '{pattern[:50]}...' 找到 {len(matches)} 个匹配")
                for i, match in enumerate(matches[:2]):
                    print(f"  {i+1}. {match[:200]}...")
        
        return html
        
    except Exception as e:
        print(f"访问失败: {e}")
        return None

if __name__ == "__main__":
    analyze_html_structure()