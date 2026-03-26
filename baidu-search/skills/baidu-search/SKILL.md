---
name: baidu-search
description: |
  百度搜索增强版：大规模搜索、智能分数筛选、内容抓取、AI总结。
  当用户要求"百度搜索"、"用百度查"、"搜索中文内容"、"baidu search"时触发。
  适合搜索中文资料、中国本土信息、企业信息、新闻资讯等。
argument-hint: <搜索关键词>
---

# 百度搜索增强版

一个完整的中文网络搜索解决方案，支持大规模搜索、智能筛选、内容抓取和 AI 总结。

## 核心功能

| 功能 | 说明 |
|-----|------|
| 大规模搜索 | 支持 100-200+ 条结果 |
| 智能筛选 | 按质量分数过滤，返回前 20% 或高于阈值的结果 |
| 内容抓取 | 自动解析百度跳转链接，抓取真实网页内容 |
| 动态网页 | 支持 Playwright 渲染 JavaScript 页面 |
| 本地存档 | 将抓取内容保存到本地文件 |
| AI 总结 | 调用 LLM 生成内容摘要和关键发现 |

## 快速开始

```bash
# 基础搜索：搜索100条，返回分数前20%
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/baidu_search.py" "苏州银行"

# 完整流程：搜索 + 抓取 + 总结 + 存档
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/baidu_search.py" "苏州银行" -n 150 -f 20 -s -o ~/search_results/suzhoubank
```

## 脚本说明

### 1. baidu_search.py - 主搜索脚本

```bash
python baidu_search.py <关键词> [选项]

参数:
  -n, --limit        搜索结果数量上限 (默认100)
  -t, --top-percent  按分数筛选前N% (默认20)
  --min-score        最低分数阈值 (默认1.0)
  -f, --fetch        抓取前N个结果的内容 (默认0=不抓取)
  -s, --summarize    调用AI总结抓取内容
  -o, --output       保存内容的目录路径
  --max-workers      并发抓取数 (默认5)
  --json             输出JSON格式
```

**示例**:
```bash
# 搜索200条，筛选分数前15%，抓取前15个，总结
python baidu_search.py "人工智能发展趋势" -n 200 -t 15 -f 15 -s -o ./ai_trend

# 仅搜索和筛选，不抓取
python baidu_search.py "苏州银行 公司简介" -n 100 -t 20
```

### 2. web_fetcher.py - 网页抓取脚本

支持静态和动态网页抓取。

```bash
python web_fetcher.py <URL...> [选项]

参数:
  -d, --dynamic    渲染模式: auto(自动), always(动态), never(静态)
  -w, --wait       动态渲染等待时间(秒)
  -t, --timeout    请求超时(秒)
  -o, --output     保存目录
  --max-workers    并发数
```

**示例**:
```bash
# 抓取单个URL
python web_fetcher.py "https://www.suzhoubank.com" -o ./output

# 抓取多个URL，自动判断是否需要动态渲染
python web_fetcher.py url1 url2 url3 -d auto -o ./output

# 强制使用动态渲染（适用于SPA页面）
python web_fetcher.py "https://spa-example.com" -d always
```

### 3. ai_summarizer.py - AI总结脚本

对本地文件或文本内容进行 AI 总结。

```bash
python ai_summarizer.py <主题> [选项]

参数:
  -i, --input    输入文件或目录
  -t, --text     直接输入文本
  -s, --style    总结风格: comprehensive/brief/extract
  --analyze      深度分析模式
  -o, --output   输出文件
```

**示例**:
```bash
# 总结目录下的所有文件
python ai_summarizer.py "苏州银行" -i ./output -o ./summary.md

# 直接总结文本
python ai_summarizer.py "Python教程" -t "Python是一种..."

# 深度分析模式
python ai_summarizer.py "人工智能" -i ./ai_articles --analyze
```

## 质量评分规则

系统根据网站类型自动计算质量分数：

| 类型 | 示例 | 分数倍率 |
|-----|------|---------|
| 官方文档 | python.org, github.com | × 2.5 |
| 技术社区 | stackoverflow, csdn | × 1.4~2.3 |
| 官方机构 | edu.cn, gov.cn | × 1.8 |
| 企业官网 | suzhoubank.com | × 2.0 |
| 低质量 | 百度贴吧 | × 0.3 |

## 环境变量配置

启用 AI 功能需要配置：

```bash
# LLM API 配置
export LLM_API_KEY="your-api-key"
export LLM_API_BASE="https://api.openai.com/v1"
export LLM_MODEL="gpt-3.5-turbo"

# 或使用 OpenAI 环境变量
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.openai.com/v1"
```

## 工作流程

```
用户输入关键词
      │
      ▼
┌─────────────────┐
│   大规模搜索    │
│   (100-200条)   │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  质量评分排序   │
│  筛选前20%      │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│   内容抓取      │
│   (支持动态页)  │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│   本地存档      │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│   AI 总结       │
│   + 关键发现    │
│   + 参考链接    │
└─────────────────┘
```

## 依赖安装

```bash
# 基础依赖
pip install requests beautifulsoup4

# 动态网页支持（可选）
pip install playwright
playwright install chromium
```