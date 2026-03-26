# Claude Code Skills 合集

为 Claude Code 提供的实用 Skill 插件集合。

## Skill 列表

### 百度搜索 (baidu-search)

中文网络搜索增强工具，支持大规模搜索、智能筛选、内容抓取和 AI 总结。

```bash
/baidu-search 关键词
/baidu-search 苏州银行 -n 100 -f 10 -s
```

### 文件搜索 (file-searcher)

在本地文件中搜索关键词，支持 Word/PDF/Markdown 等多种格式。

```bash
/file-searcher 关键词
/file-searcher 外包 --path C:\Documents --ext docx,pdf
```

## 安装方法

### 方法一：添加 Marketplace 后安装（推荐）

**步骤 1：添加 Marketplace**

在 Claude Code 中运行：
```
/marketplace add https://github.com/sjerold/cc-skills.git
```

**步骤 2：安装插件**
```
/marketplace
```
打开 marketplace 界面，找到 `cc-skills`，选择要安装的插件。

### 方法二：手动安装

```bash
# 克隆仓库
git clone https://github.com/sjerold/cc-skills.git

# 复制插件到 Claude 插件目录
cp -r cc-skills/skills/baidu-search ~/.claude/plugins/
cp -r cc-skills/skills/file-searcher ~/.claude/plugins/

# 安装 Python 依赖
pip install -r cc-skills/skills/baidu-search/requirements.txt
pip install -r cc-skills/skills/file-searcher/requirements.txt
```

### 方法三：Windows 一键安装

下载仓库后双击 `install.bat`。

## 目录结构

```
cc-skills/
├── .claude-plugin/
│   └── marketplace.json     # Marketplace 配置
├── skills/
│   ├── baidu-search/        # 百度搜索 Skill
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   ├── skills/
│   │   │   └── SKILL.md
│   │   ├── scripts/
│   │   └── requirements.txt
│   │
│   └── file-searcher/       # 文件搜索 Skill
│       └── ...
│
├── install.bat
└── pack.bat
```

## 依赖要求

- Python 3.8+
- 百度搜索：`requests`, `beautifulsoup4`
- 文件搜索：`python-docx`, `PyPDF2`

## License

MIT
