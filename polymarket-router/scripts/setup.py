#!/usr/bin/env python3
"""
PolyMarket多源数据集成路由系统安装脚本
"""

from setuptools import setup, find_packages
import os

# 读取README文件
with open('../references/README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# 读取requirements.txt
with open('../requirements.txt', 'r', encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="polymarket-router",
    version="1.0.0",
    author="PolyMarket Router Team",
    author_email="team@polymarket-router.com",
    description="多源PolyMarket数据集成路由系统，确保下游应用无缝获取预测市场数据",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/polymarket-router/polymarket-router",
    packages=find_packages(where='.'),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "flake8>=6.1.0",
            "mypy>=1.5.0",
        ],
        "redis": [
            "redis>=4.5.0",
        ],
        "monitoring": [
            "prometheus-client>=0.16.0",
            "structlog>=23.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "polymarket-router=polymarket_router.cli:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/polymarket-router/polymarket-router/issues",
        "Source": "https://github.com/polymarket-router/polymarket-router",
        "Documentation": "https://polymarket-router.readthedocs.io/",
    },
)