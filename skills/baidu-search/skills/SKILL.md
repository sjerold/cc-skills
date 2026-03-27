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

## 环境检查

**在执行搜索前，先检查环境是否已配置：**

```bash
# 检查 dsbot_env 是否存在
conda env list | grep dsbot_env

# 如果不存在，运行 setup
cmd /c "$PLUGIN_DIR/scripts/setup_env.bat"
```

或者直接运行 setup 命令：
```bash
/baidu-setup
```

## 执行搜索

环境配置完成后，运行：

```bash
# 获取 Python 路径
PYTHON_PATH=$(cat "$PLUGIN_DIR/.python_path" 2>/dev/null || echo "")

# 如果没有保存的路径，尝试从 conda 获取
if [ -z "$PYTHON_PATH" ]; then
    PYTHON_PATH=$(conda run -n dsbot_env python -c "import sys; print(sys.executable)" 2>/dev/null)
fi

# 如果还是没有，提示运行 setup
if [ -z "$PYTHON_PATH" ]; then
    echo "请先运行 /baidu-setup 安装环境"
    exit 1
fi

# 执行搜索
"$PYTHON_PATH" "$PLUGIN_DIR/scripts/baidu_search.py" "$ARGUMENTS"
```

**Windows 用户直接运行：**
```cmd
cmd /c "if exist %PLUGIN_DIR%\.python_path (set /p PYTHON=<%PLUGIN_DIR%\.python_path) else (set PYTHON=) && if not defined PYTHON (conda run -n dsbot_env python -c \"import sys; print(sys.executable)\" > %TEMP%\python_path.txt && set /p PYTHON=<%TEMP%\python_path.txt) && %PYTHON% %PLUGIN_DIR%\scripts\baidu_search.py %ARGUMENTS%"
```

## 核心功能

| 功能 | 说明 |
|-----|------|
| 大规模搜索 | 支持 100-200+ 条结果 |
| 智能筛选 | 按质量分数过滤，返回前 20% 或高于阈值的结果 |
| 内容抓取 | 自动解析百度跳转链接，抓取真实网页内容 |
| 动态网页 | 支持 Playwright 渲染 JavaScript 页面 |
| 本地存档 | 将抓取内容保存到本地文件 |
| AI 总结 | 调用 LLM 生成内容摘要和关键发现 |

## 参数说明

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

## 示例

```bash
# 基础搜索
/baidu-search 苏州银行

# 搜索200条，筛选前15%，抓取15个，总结
/baidu-search 人工智能发展趋势 -n 200 -t 15 -f 15 -s -o ./ai_trend

# 只搜索和筛选
/baidu-search 苏州银行 公司简介 -n 100 -t 20
```

## 质量评分规则

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
export LLM_API_KEY="your-api-key"
export LLM_API_BASE="https://api.openai.com/v1"
export LLM_MODEL="gpt-3.5-turbo"
```
