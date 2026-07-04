---
name: skill-audit
description: "全面审计 WorkBuddy Skill 的方法论工具。通过10轮标准化流程—代码审查、测试修复、数据去重、文档一致性—系统性发现并修复 Bug、死代码、冗余和架构健康问题。审计完成后输出结构化报告。"
agent_created: true
---

# Skill Audit — WorkBuddy Skill 全面审计方法论

审计一个 WorkBuddy Skill 的核心代码质量、架构健康度和测试完整性。覆盖维度包括死代码清理、导入路径安全、测试基线修复、数据源去重、文档一致性。

## 何时使用

- 用户要求"全面审查"、"不留技术债"、"彻底修复"某个 Skill
- 发现某个 Skill 出现重复出现的测试失败
- 接手一个不熟悉的 Skill 需要快速建立基线

## 强制审计流程（10轮）

### 审计前准备

1. 加载目标 Skill：用 Skill 命令加载其 SKILL.md
2. 理解架构约定：留意 SKILL.md 中的架构要求（如"评分逻辑单源真理原则"）
3. 设置工作目录：目标 Skill 的根目录

### 第1轮：基线扫描

1. 扫描目录结构：文件数/行数/目录深度
2. 查找异常：`__pycache__`、`.bak`、`.orig`、空目录、`Temp/`、运行时产物
3. 运行全量测试：`python -m pytest tests/ -v --tb=short`，记录通过/失败数
4. 运行专用 lint：如存在专用合规检测脚本则运行
5. **记录 baseline**

```bash
# 目录结构
find . -name "*.py" | wc -l
wc -l $(find . -name "*.py")
du -sh .

# 缓存/垃圾
find . -name "__pycache__" -type d
find . -name "*.bak" -o -name "*.orig"

# 全量测试
python -m pytest tests/ -q --tb=no

# 专用 lint（如果存在）
python scripts/lint_no_inline_scoring.py
```

### 第2轮：Import 链审查

1. 提取所有 `from X import Y` / `import X` 语句
2. 分类：裸 import（`from indicators import`）vs 包式 import（`from scripts.indicators import`）
3. 检测硬编码绝对路径（`r"C:\Users\..."`、`r"/home/..."`）
4. 检测 `os.chdir()`、`sys.path.insert()` 模式
5. 对每个检测到的问题：
   - 裸 import → 添加 `try: from scripts.X import Y / except: from X import Y`
   - 硬编码路径 → 替换为 `os.path.dirname(os.path.abspath(__file__))` 或 `os.path.expanduser("~")`
   - `os.chdir()` → 替换为纯 path 方案

### 第3轮：逐模块审计（按大小降序）

1. 按行数排序找出最大文件
2. 对每个模块：
   - 检查模块级 import 是否安全
   - 检查是否有 deprecated 函数包含大量内联逻辑
   - 检查是否有内联评分/阈值逻辑（如果 SKILL.md 要求单一来源）
   - 检查是否有硬编码列表应统一至单一来源
3. 记录每个模块的发现分级：
   - 🔴 Bug：会导致 crash 或错误结果
   - 🟡 冗余：重复代码/数据
   - ⚪ 技术债：标记 deprecated、设计问题

### 第4轮：测试修复

如果测试 baseline 有失败：
1. 分析每个失败的原因模式（权重不匹配、接口变更、输出字段变化）
2. 批量修复：逐测试更新断言值
3. 对 v2.x 版本升级导致的批量失败，用 map 模式修复
4. 对已移除特性的测试，标记为 `@unittest.skip("原因")`

### 第5轮：数据去重

1. 查找跨文件的重复定义（品种列表、配置常量等）
2. 确定单一来源
3. 将重复定义移至单一来源文件
4. 引用方改为程序化派生

### 第6-9轮：迭代深入

5-9 轮逐轮降低发现量。每轮标准：
- 发现 ≥ 3 项 → 继续深入
- 发现 1-2 项 → 修复后继续
- 发现 0 项，且测试全绿 → 可停止

### 第10轮：终验

1. 全量测试运行，确认 0 新增失败
2. 清理所有 `__pycache__`
3. 输出审计报告（Markdown）

### 审计报告模板

每次审计后输出结构化报告：

```markdown
## {skill-name} 审计报告

**Bug 修复**: N 个
- 描述每个修复

**测试变化**: X → Y pass (Z fail)
- 失败原因说明

**清理统计**:
- 文件数: A → B (-C)
- 代码行: D → E (-F)
- 磁盘: G → H

**剩余技术债**:
- 已知但未修复的问题
```
