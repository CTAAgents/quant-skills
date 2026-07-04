# SkillAdaptor

基于论文 "SkillAdaptor: Self-Adapting Skills for LLM Agents from Trajectories" (arXiv:2606.01311) 的 Python 实现。

## 概述

SkillAdaptor 是一个免训练的、步级别的技能适应框架，具有显式的故障归因能力。它可以：

1. **分析 LLM 智能体的执行轨迹** - 解析和理解智能体的状态、动作、奖励等
2. **识别故障步骤并归因责任** - 定位第一个可操作的故障，并确定哪些技能应该负责
3. **生成有针对性的技能更新** - 基于故障信息提出技能改进建议
4. **支持接受检查机制** - 在应用更新前进行验证

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

```python
from skill_adaptor import SkillAdaptor

# 初始化
adaptor = SkillAdaptor()

# 运行完整分析流程
result = adaptor.run("data/example_trajectory.json")

# 查看结果
print(f"是否检测到故障: {result['fault_attribution']['has_fault']}")
```

更多示例请查看 `examples/` 目录。

## 目录结构

```
skill-adaptor/
├── __init__.py              # 主模块入口
├── core/                    # 核心功能
│   ├── __init__.py
│   ├── trajectory_analyzer.py   # 轨迹分析器
│   ├── fault_attributor.py      # 故障归因器
│   └── skill_adapter.py         # 技能适配器
├── examples/                # 示例代码
│   ├── basic_usage.py
│   └── load_from_file.py
├── data/                    # 数据文件
│   └── example_trajectory.json
├── tests/                   # 测试用例
├── references/              # 参考资料
│   ├── SkillAdaptor_paper.pdf  # 原论文
│   └── SkillAdaptor_github/    # GitHub 源码
├── download_resources.py    # 下载参考资料脚本
├── requirements.txt
├── README.md
├── WORKFLOW.md
└── SKILL.md
```

## 运行测试

```bash
python -m pytest tests/ -v
```

或单独运行各个测试文件：

```bash
python tests/test_trajectory_analyzer.py
python tests/test_fault_attributor.py
python tests/test_integration.py
```

## 下载参考资料

如果需要重新下载论文和GitHub源码：

```bash
python download_resources.py
```

## 论文引用

```
@article{yu2026skilladaptor,
  title={SkillAdaptor: Self-Adapting Skills for LLM Agents from Trajectories},
  author={Yu, Zhuoyun and Xie, Xin and Yao, Wuguannan and Wang, Chenxi and Liang, Lei and Qi, Xiang and Deng, Shumin},
  journal={arXiv preprint arXiv:2606.01311},
  year={2026}
}
```

## 许可证

MIT
