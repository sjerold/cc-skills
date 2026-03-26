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

### 方法一：Marketplace 安装（推荐）

```bash
# 1. 添加 Marketplace
/marketplace add https://github.com/sjerold/cc-skills.git

# 2. 打开 Marketplace 界面安装
/marketplace
```

### 方法二：手动安装（Windows）

1. 下载仓库 ZIP 或克隆
2. 解压后双击运行 `install.bat`
3. 脚本会自动：
   - 检测/安装 Miniconda
   - 创建 `dsbot_env` Conda 环境
   - 安装 Python 依赖
   - 复制插件到 `~/.claude/plugins/`

### 方法三：手动安装（Mac/Linux）

```bash
# 克隆仓库
git clone https://github.com/sjerold/cc-skills.git
cd cc-skills

# 创建 Conda 环境
conda env create -f skills/baidu-search/environment.yml

# 复制插件
cp -r skills/baidu-search ~/.claude/plugins/
cp -r skills/file-searcher ~/.claude/plugins/

# 设置环境变量
echo 'export CONDA_PYTHON="$HOME/miniconda3/envs/dsbot_env/bin/python"' >> ~/.bashrc
```

## 环境要求

- **Miniconda/Anaconda** (自动安装)
- **dsbot_env** 环境 (自动创建)
- Python 3.10+

## 目录结构

```
cc-skills/
├── .claude-plugin/
│   └── marketplace.json
├── skills/
│   ├── baidu-search/
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   ├── skills/
│   │   │   └── SKILL.md
│   │   ├── scripts/
│   │   │   ├── baidu_search.py
│   │   │   ├── web_fetcher.py
│   │   │   └── ai_summarizer.py
│   │   ├── environment.yml      # Conda 环境配置
│   │   └── requirements.txt
│   │
│   └── file-searcher/
│       ├── ...
│       └── environment.yml
│
├── install.bat    # Windows 安装脚本
└── pack.bat       # 打包脚本
```

## License

MIT
