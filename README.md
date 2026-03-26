# Claude Code 插件合集

为 Claude Code 提供的实用插件集合。

## 插件列表

### 1. 百度搜索 (baidu-search)

中文网络搜索增强工具，支持大规模搜索、智能筛选、内容抓取和 AI 总结。

**功能特性：**
- 大规模搜索：支持 100-200+ 条结果
- 智能筛选：按质量分数过滤
- 内容抓取：支持静态和动态网页
- AI 总结：调用 LLM 生成摘要

```bash
/baidu-search 关键词
/baidu-search 苏州银行 -n 100 -f 10 -s
```

### 2. 文件搜索 (file-searcher)

在本地文件中搜索关键词，支持多种文档格式。

**支持格式：**
- Word (.docx)
- PDF (.pdf)
- Markdown (.md)
- 文本文件 (.txt, .json, .csv 等)
- 代码文件 (.py, .js, .java 等)

```bash
/file-searcher 关键词
/file-searcher 外包 --path C:\Documents --ext docx,pdf
```

## 安装方法

### 方法一：直接下载

1. 下载对应插件的 ZIP 文件
2. 解压到任意目录
3. 双击运行 `install.bat`

### 方法二：手动安装

1. 将插件目录复制到：
   - Windows: `C:\Users\<用户名>\.claude\plugins\`
   - Mac/Linux: `~/.claude/plugins/`

2. 安装 Python 依赖：
```bash
# 百度搜索插件
pip install requests beautifulsoup4

# 文件搜索插件
pip install python-docx PyPDF2
```

## 依赖要求

- Python 3.8+
- 百度搜索：`requests`, `beautifulsoup4`
- 文件搜索：`python-docx`, `PyPDF2`

## 目录结构

```
plugins/
├── baidu-search/
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── scripts/
│   │   ├── baidu_search.py
│   │   ├── web_fetcher.py
│   │   └── ai_summarizer.py
│   └── skills/baidu-search/
│       └── SKILL.md
│
├── file-searcher/
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── scripts/
│   │   └── file_searcher.py
│   └── skills/file-searcher/
│       └── SKILL.md
│
├── pack.bat              # 打包脚本
├── install.bat           # 安装脚本
├── requirements.txt      # 百度搜索依赖
└── requirements-file-searcher.txt  # 文件搜索依赖
```

## License

MIT