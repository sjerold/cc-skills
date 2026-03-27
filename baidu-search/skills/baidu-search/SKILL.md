---
name: baidu-search
description: |
  百度搜索增强版：大规模搜索、智能分数筛选、内容抓取、自动总结。
  当用户要求"百度搜索"、"用百度查"、"搜索中文内容"、"baidu search"时触发。
  适合搜索中文资料、中国本土信息、企业信息、新闻资讯等。
argument-hint: <搜索关键词>
---

# 百度搜索增强版

一个完整的中文网络搜索解决方案，支持大规模搜索、智能筛选、内容抓取和自动总结。

## 核心功能

| 功能 | 说明 |
|-----|------|
| 大规模搜索 | 默认搜索 150 条结果 |
| 智能筛选 | 按质量分数自动筛选前 35% 进行抓取 |
| Session 管理 | 每次搜索生成唯一 session_id，文件独立保存 |
| 内容抓取 | 使用 Playwright 渲染动态页面 |
| 本地存档 | 抓取内容保存为 Markdown 文件 |
| 自动总结 | 读取所有 md 文件，生成整合报告 |

## 快速开始

```bash
# 一键搜索（自动完成所有流程）
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/baidu_search.py" "数字人民币 2026"

# 指定搜索数量和筛选比例
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/baidu_search.py" "苏州银行" -n 100 -t 40
```

## 命令参数

```bash
python baidu_search.py <关键词> [选项]

参数:
  <关键词>           搜索关键词
  -n, --limit        搜索结果数量 (默认150)
  -t, --top-percent  按分数筛选前N%的结果进行抓取 (默认35)
  --min-score        最低分数阈值 (默认1.0)
  -o, --output       保存目录 (默认 ~/Downloads/baidu_search/<session_id>)
  --session-id       指定会话ID
  --no-summarize     不生成总结报告
  --json             输出JSON格式
  --show-browser     显示浏览器窗口（用于处理验证码）
  --close            关闭所有调试Chrome进程
```

## 使用示例

```bash
# 默认搜索：150条结果，自动抓取前35%
python baidu_search.py "人工智能发展趋势"

# 搜索100条，抓取分数前40%
python baidu_search.py "苏州银行" -n 100 -t 40

# 指定保存目录
python baidu_search.py "数字货币" -o ./my_search

# 仅搜索不生成总结
python baidu_search.py "测试关键词" --no-summarize
```

## 输出文件结构

每次搜索会在 `~/Downloads/baidu_search/<session_id>/` 目录下生成：

```
20260327_102254_d0969214/
├── 网页标题1_abc123.md        # 抓取的网页内容
├── 网页标题2_def456.md
├── ...
├── 搜索报告_20260327_102254_d0969214.md  # 详细报告
└── 搜索总结_20260327_102254_d0969214.md  # 整合总结
```

### 文件说明

- **网页内容文件**: 每个抓取的网页保存为单独的 `.md` 文件
- **搜索报告**: 包含所有搜索结果、参考链接、内容预览
- **搜索总结**: 整合所有抓取内容，生成结构化总结

## 质量评分规则

系统根据网站类型自动计算质量分数：

| 类型 | 示例 | 分数倍率 |
|-----|------|---------|
| 官方文档 | python.org, github.com | × 2.5 |
| 官方机构 | edu.cn, gov.cn | × 1.8 |
| 技术社区 | csdn, zhihu, juejin | × 1.4~2.3 |
| 企业官网 | 官方网站 | × 2.0 |
| 新闻媒体 | sina, qq, sohu | × 1.5 |
| 低质量 | 贴吧、论坛灌水 | × 0.3 |

## 工作流程

```
用户输入关键词
      │
      ▼
┌─────────────────┐
│   大规模搜索    │
│   (默认150条)   │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  质量评分排序   │
│  筛选前35%      │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  Playwright抓取 │
│   (支持动态页)  │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  保存为md文件   │
│  (session目录)  │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│   读取所有md    │
│   生成总结报告  │
└─────────────────┘
```

## 环境配置

### 方式一：使用 Miniconda + dsbot_env（推荐）

```bash
# 1. 安装 Miniconda（如未安装）
# Windows: 下载 https://docs.conda.io/en/latest/miniconda.html

# 2. 创建虚拟环境
conda create -n dsbot_env python=3.10 -y
conda activate dsbot_env

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 Playwright 浏览器
playwright install chromium
```

### 方式二：直接安装

```bash
# 基础依赖
pip install requests beautifulsoup4

# 动态网页支持
pip install playwright
playwright install chromium
```

### 依赖包版本

```
requests>=2.28.0
beautifulsoup4>=4.12.0
playwright>=1.40.0
```

### 运行命令

```bash
# 使用 dsbot_env 环境
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/baidu_search.py" "关键词"
```